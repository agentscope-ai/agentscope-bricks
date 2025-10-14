# -*- coding: utf-8 -*-
import json
import os
import queue
import time
import threading
from typing import Tuple, List
from dataclasses import dataclass

from openai import Stream
from openai.types.chat import ChatCompletionChunk
from openai.types.chat.chat_completion_chunk import ChoiceDeltaToolCall
from pydantic import BaseModel
from concurrent.futures import ThreadPoolExecutor

from asr_client_factory import AsrClientFactory
from agentscope_bricks.components.RAGs.modelstudio_rag import (
    ModelstudioRag,
    RagInput,
)
from agentscope_bricks.components.memory.local_memory import SimpleChatStore
from agentscope_bricks.components.realtime_clients.realtime_component import (
    RealtimeState,
)
from text_chat_flow import TextChatFlow
from tts_client_factory import (
    TtsClientFactory,
    TtsClientPool,
)
from agentscope_bricks.models.llm import BaseLLM
from agentscope_bricks.utils.schemas.realtime import (
    ModelstudioVoiceChatSessionStartedPayload,
    ModelstudioVoiceChatSessionStartPayload,
    ModelstudioVoiceChatUpstream,
    ModelstudioVoiceChatDownstream,
    ModelstudioVoiceChatSessionStopPayload,
    ModelstudioVoiceChatResponseAudioStartedPayload,
    ModelstudioVoiceChatResponseAudioStoppedPayload,
    ModelstudioVoiceChatSessionStoppedPayload,
    ModelstudioVoiceChatAudioTranscriptPayload,
    ModelstudioVoiceChatResponseTextPayload,
    TtsVendor,
    ModelstudioVoiceChatRequest,
    ModelstudioVoiceChatDirective,
    ModelstudioVoiceChatParameters,
    ModelstudioVoiceChatResponse,
    ModelstudioVoiceChatEvent,
)
from agentscope_bricks.utils.server_utils.fastapi_websocket_server import (
    FastApiWebsocketServer,
    RealtimeService,
)
from starlette.websockets import WebSocket
from agentscope_bricks.utils.logger_util import logger
from agentscope_bricks.utils.message_util import merge_incremental_chunk
from async_task_executor import (
    AsyncTaskExecutor,
)
from agentscope_bricks.utils.schemas.oai_llm import (
    AssistantMessage,
    UserMessage,
    OpenAIMessage,
)


class AsrEvent(BaseModel):
    event_time: float
    text: str
    sentence_id: str
    is_sentence_end: bool


@dataclass
class DataStats:
    log_count_period: int = 1
    count: int = 0
    prev_time: int = int(time.time() * 1000)


class VoiceChatService(RealtimeService):
    def __init__(self, websocket: WebSocket):
        super().__init__(websocket)
        self._asr_client = None
        self._tts_clients = {}
        self._rag_component = ModelstudioRag()
        self._tts_audio_queue = queue.Queue()
        self._output_file_dir = (
            os.path.expanduser(os.environ.get("OUTPUT_FILE_DIR"))
            if os.environ.get("OUTPUT_FILE_DIR")
            else None
        )
        self._output_file_streams = {}
        self._parameters = ModelstudioVoiceChatParameters()
        self._upstream = ModelstudioVoiceChatUpstream()
        self._downstream = ModelstudioVoiceChatDownstream()
        self._session_id = None
        self._cancel_chat_ids = []
        self._asr_events = []
        self._chat_store = SimpleChatStore()
        self._tools = []
        self._thread_executor = ThreadPoolExecutor(max_workers=5)
        self._async_executor = AsyncTaskExecutor(self._thread_executor)
        self._input_stats = DataStats(log_count_period=10)
        self._tts_output_stats = DataStats(log_count_period=10)
        self._tts_client_pool = None
        self._tts_clients_lock = threading.Lock()
        logger.info("create voice chat")

    async def process_message(self, request: ModelstudioVoiceChatRequest):
        logger.info(
            "voice chat process message: %s"
            % json.dumps(request.model_dump(), ensure_ascii=False),
        )
        directive = request.directive
        payload = request.payload
        if directive == ModelstudioVoiceChatDirective.SESSION_START:
            await self._start(payload)
        elif directive == ModelstudioVoiceChatDirective.SESSION_STOP:
            await self._stop(payload)
        else:
            logger.error("unknown directive: %s" % directive)

    async def process_data(self, data: bytes):
        if self.state == RealtimeState.IDLE:
            logger.info("ignore data: length=%d" % len(data))
            return

        if self._input_stats.count % self._input_stats.log_count_period == 0:
            curr_time = int(time.time() * 1000)
            logger.info(
                "input_audio: count=%d, avg_interval=%d, length=%d"
                % (
                    self._input_stats.count,
                    (curr_time - self._input_stats.prev_time)
                    / self._input_stats.log_count_period,
                    len(data),
                ),
            )
            self._input_stats.prev_time = curr_time
        self._input_stats.count += 1

        self._asr_client.send_audio_data(data)

    async def destroy(self):
        if self._asr_client:
            self._asr_client.close()
            self._asr_client = None

        for tts_chat_id in self._tts_clients:
            self._tts_clients[tts_chat_id].close()
        self._tts_clients.clear()

    async def _start(self, payload: ModelstudioVoiceChatSessionStartPayload):
        logger.info(
            "voice chat start: %s"
            % json.dumps(payload.model_dump(), ensure_ascii=False),
        )
        self.state = RealtimeState.RUNNING

        self._session_id = payload.session_id
        self._upstream = payload.upstream
        self._downstream = payload.downstream
        self._parameters = payload.parameters

        self._upstream.asr_options = AsrClientFactory.get_config(
            self._upstream.asr_vendor,
            self._upstream.asr_options,
        )
        self._downstream.tts_options = TtsClientFactory.get_config(
            self._downstream.tts_vendor,
            self._downstream.tts_options,
        )

        tts_callbacks = {
            "on_data": self._on_tts_data,
            "on_complete": self._on_tts_complete,
        }
        if self._downstream.tts_vendor == TtsVendor.AZURE:
            self._tts_client_pool = TtsClientPool()
            self._tts_client_pool.initialize(
                1,
                self._downstream.tts_vendor,
                self._downstream.tts_options,
                tts_callbacks,
            )

        self._thread_executor.submit(self._output_stream_cycle)

        asr_callbacks = {"on_event": self._on_asr_event}

        self._asr_client = AsrClientFactory.create_client(
            self._upstream.asr_vendor,
            self._upstream.asr_options,
            asr_callbacks,
        )

        self._asr_client.start()

        if self._parameters.enable_tool_call is True:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            tools_dir = os.path.join(current_dir, "tools")
            self._tools = self._load_tools(tools_dir)

        await self._send_text(self._create_session_started())

    async def _stop(self, payload: ModelstudioVoiceChatSessionStopPayload):
        logger.info(
            "voice chat stop: request=%s"
            % json.dumps(payload.model_dump(), ensure_ascii=False),
        )
        if self.state == RealtimeState.IDLE:
            return

        self.state = RealtimeState.IDLE

        await self.destroy()

        await self._send_text(self._create_session_stopped())

        if self._asr_client:
            self._asr_client.stop()

        # Clean up all TTS clients
        with self._tts_clients_lock:
            for chat_id in list(self._tts_clients.keys()):
                if chat_id in self._tts_clients:
                    self._tts_clients[chat_id].close()
                    self._tts_clients.pop(chat_id, None)

        if self._tts_client_pool:
            self._tts_client_pool.release()
            self._tts_client_pool = None

    async def _send_text(self, text: str):
        logger.info("send_text: {%s}" % text)
        await self.ws.send_text(text)

    async def _send_data(self, data: bytes):
        await self.ws.send_bytes(data)

    def _chat_process(self, text: str, chat_id: str):

        logger.info("chat_start: chat_id=%s, text=%s" % (chat_id, text))

        if "audio" in self._downstream.modalities:
            self._thread_executor.submit(self._start_tts_client, chat_id)

        ttft_first_resp = True
        first_resp = True
        cumulated_responses = []
        chat_start_time = int(time.time() * 1000)
        chat_id, responses = self._chat_llm(text, chat_id)
        # chat_id, responses = self._chat_rag_with_llm(text, chat_id)
        for response in responses:
            # logger.info("chat_response: chat_id=%s, response=%s" %
            # (chat_id, json.dumps(response.model_dump(), ensure_ascii=False)))
            logger.info(
                "chat_response: chat_id=%s, response=%s"
                % (
                    chat_id,
                    json.dumps(response.model_dump(), ensure_ascii=False),
                ),
            )

            if ttft_first_resp:
                logger.info(
                    "chat_ttft: chat_id=%s, ttft=%s"
                    % (chat_id, int(time.time() * 1000) - chat_start_time),
                )
                ttft_first_resp = False

            is_canceled = chat_id in self._cancel_chat_ids
            if is_canceled:
                logger.info(
                    "cancel_chat_response: chat_id=%s, response=%s"
                    % (
                        chat_id,
                        json.dumps(response.model_dump(), ensure_ascii=False),
                    ),
                )
                continue

            tool_calls = response.choices[0].delta.tool_calls
            # content = response["output"]["choices"][0]["message"]["content"]
            content = response.choices[0].delta.content
            finished = (
                response.choices[0].finish_reason == "stop"
                or response.choices[0].finish_reason == "tool_calls"
            )

            if tool_calls:
                if chat_id and chat_id in self._tts_clients:
                    self._tts_clients[chat_id].close()
                    self._tts_clients.pop(chat_id)
            else:
                tool_calls = []

            if "text" in self._downstream.modalities:
                if first_resp:
                    audio_transcript = self._create_audio_transcript(
                        "",
                        True,
                    )
                    self._async_executor.submit(
                        self._send_text,
                        audio_transcript,
                    )

                resp_msg = self._create_response_text(
                    content,
                    tool_calls,
                    finished,
                )
                self._async_executor.submit(self._send_text, resp_msg)

            if chat_id and chat_id in self._tts_clients:
                self._tts_clients[chat_id].send_text_data(content)

            first_resp = False

            cumulated_responses.append(response)

        if chat_id and chat_id in self._cancel_chat_ids:
            self._cancel_chat_ids.remove(chat_id)
        else:
            merged_response = merge_incremental_chunk(cumulated_responses)
            messages = self.convert_chat_completion_chunk_to_messages(
                merged_response,
                text,
            )
            self._chat_store.add_messages(self._session_id, messages)

        if chat_id:
            with self._tts_clients_lock:
                if chat_id in self._tts_clients:
                    # Ensure TTS client is completed before cleanup
                    tts_client = self._tts_clients[chat_id]
                    tts_client.async_stop()
                    # Wait a short time to ensure async stop completes
                    time.sleep(0.1)

        logger.info("chat_end: chat_id=%s, text=%s" % (chat_id, text))

    def _output_stream_cycle(self):
        logger.info(
            "output stream cycle begin: session_id=%s" % self._session_id,
        )
        send_times = 0
        sample_rate = self._downstream.tts_options.sample_rate
        last_send_time = int(time.time() * 1000)
        while self.state == RealtimeState.RUNNING:
            start_time = time.time()
            if self._tts_audio_queue.empty():
                time.sleep(0.02)
                continue

            chat_id, data_index, frame = self._tts_audio_queue.get()

            if data_index == -1:
                logger.info(
                    "send_audio_done: session_id=%s, chat_id=%s, data_index=%d"
                    % (self._session_id, chat_id, data_index),
                )
                resp = ModelstudioVoiceChatResponse(
                    event=ModelstudioVoiceChatEvent.RESPONSE_AUDIO_ENDED,
                    payload=ModelstudioVoiceChatResponseAudioStoppedPayload(
                        session_id=self._session_id,
                    ),
                )
                self._async_executor.submit(
                    self._send_text,
                    json.dumps(resp.model_dump(), ensure_ascii=False),
                )
                continue

            if chat_id in self._cancel_chat_ids:
                logger.info(
                    "cancel_send_audio: session_id=%s, chat_id=%s,"
                    " data_index=%d" % (self._session_id, chat_id, data_index),
                )
                continue

            if data_index == 0:
                logger.info(
                    "send_audio_start: session_id=%s, chat_id=%s,"
                    " data_index=%d" % (self._session_id, chat_id, data_index),
                )
                resp = ModelstudioVoiceChatResponse(
                    event=ModelstudioVoiceChatEvent.RESPONSE_AUDIO_STARTED,
                    payload=ModelstudioVoiceChatResponseAudioStartedPayload(
                        session_id=self._session_id,
                    ),
                )
                self._async_executor.submit(
                    self._send_text,
                    json.dumps(resp.model_dump(), ensure_ascii=False),
                )

            frame_time = len(frame) / sample_rate / 2.0

            if send_times % 20 == 0:
                curr_send_time = int(time.time() * 1000)
                logger.info(
                    "send_audio_data: session_id=%s, chat_id=%s, size=%d,"
                    " index=%d, duration=%d, interval=%d"
                    % (
                        self._session_id,
                        chat_id,
                        len(frame),
                        data_index,
                        int(frame_time * 1000),
                        curr_send_time - last_send_time,
                    ),
                )
                last_send_time = curr_send_time

            self._async_executor.submit(self._send_data, frame)

            elapsed_time = time.time() - start_time
            sleep_time = frame_time - elapsed_time - 0.02

            if sleep_time > 0:
                time.sleep(sleep_time)

            send_times += 1

        logger.info(
            "output stream cycle end: session_id=%s" % self._session_id,
        )

    def _start_tts_client(self, chat_id):
        try:
            with self._tts_clients_lock:
                # Clean up completed or cancelled TTS clients, not all clients
                tts_to_remove = []
                for tts_chat_id in self._tts_clients:
                    client = self._tts_clients[tts_chat_id]
                    # Check client status, clean up if completed or idle
                    if (
                        hasattr(client, "state")
                        and client.state == RealtimeState.IDLE
                    ):
                        client.close()
                        tts_to_remove.append(tts_chat_id)

                for tts_chat_id in tts_to_remove:
                    self._tts_clients.pop(tts_chat_id, None)

                # If current chat_id already has TTS client, reuse it directly
                if chat_id in self._tts_clients:
                    return

            self._downstream.tts_options.chat_id = chat_id
            callbacks = {
                "on_data": self._on_tts_data,
                "on_complete": self._on_tts_complete,
            }
            if self._tts_client_pool:
                tts_client = self._tts_client_pool.get()
                if tts_client is None:
                    logger.error("Failed to get TTS client from pool")
                    return
                # Ensure client's chat_id is set correctly
                tts_client.set_chat_id(chat_id)
            else:
                tts_client = TtsClientFactory.create_client(
                    self._downstream.tts_vendor,
                    self._downstream.tts_options,
                    callbacks,
                )
            tts_client.start()

            with self._tts_clients_lock:
                self._tts_clients[chat_id] = tts_client
        except Exception as e:
            logger.error(
                "Error starting TTS client for chat_id=%s: %s"
                % (chat_id, str(e)),
            )

    def _cancel_tts(self, chat_id):
        logger.info("cancel tts: chat_id=%s" % chat_id)
        with self._tts_clients_lock:
            if chat_id in self._tts_clients:
                self._tts_clients[chat_id].close()
                self._tts_clients.pop(chat_id, None)

    def _on_asr_event(self, sentence_end: bool, sentence_text: str) -> None:
        asr_event_time = int(round(time.time() * 1000))

        chat_text = sentence_text
        vad_duration = None

        if not self._asr_events:
            sentence_id = "0"
        else:
            if self._asr_events[-1].is_sentence_end:
                vad_duration = asr_event_time - self._asr_events[-1].event_time
                sentence_id = str(int(self._asr_events[-1].sentence_id) + 1)
                if (
                    self._upstream.asr_options.fast_vad_max_duration is None
                    or vad_duration
                    >= self._upstream.asr_options.fast_vad_max_duration
                ):
                    self._asr_events.clear()
                else:
                    for event in self._asr_events:
                        if event.is_sentence_end:
                            self._cancel_chat_ids.append(event.sentence_id)
            else:
                sentence_id = self._asr_events[-1].sentence_id

            if sentence_end is True:
                chat_text = (
                    "".join(
                        [
                            event.text
                            for event in self._asr_events
                            if event.is_sentence_end
                        ],
                    )
                    + sentence_text
                )

        logger.info(
            f"on_asr_event: end={sentence_end}, sentence_id={sentence_id},"
            f" vad_duration={vad_duration}, text={sentence_text},"
            f" tts_client_size={len(self._tts_clients)}",
        )

        self._asr_events.append(
            AsrEvent(
                event_time=asr_event_time,
                text=sentence_text,
                sentence_id=sentence_id,
                is_sentence_end=sentence_end,
            ),
        )

        # interrupt
        with self._tts_clients_lock:
            tts_to_cancel = []
            for tts_chat_id in self._tts_clients:
                tts_to_cancel.append(tts_chat_id)

            for tts_chat_id in tts_to_cancel:
                client = self._tts_clients.get(tts_chat_id)
                if client:
                    client.close()
                    self._tts_clients.pop(tts_chat_id, None)

        if not self._tts_audio_queue.empty():
            logger.info(
                "interruption_clear_queue: queue_size=%d"
                % self._tts_audio_queue.qsize(),
            )
            chat_id = None
            while not self._tts_audio_queue.empty():
                chat_id, data_index, frame = self._tts_audio_queue.get()

            if chat_id:
                # to send ResponseAudioEnded
                self._on_tts_complete(chat_id)

        if sentence_end is True:
            self._thread_executor.submit(
                self._chat_process,
                chat_text,
                sentence_id,
            )
            audio_transcript = self._create_audio_transcript(
                chat_text,
                False,
            )
            self._async_executor.submit(self._send_text, audio_transcript)

    def _on_tts_data(self, data: bytes, chat_id: str, data_index: int) -> None:
        if (
            self._tts_output_stats.count
            % self._tts_output_stats.log_count_period
            == 0
        ):
            curr_time = int(time.time() * 1000)
            logger.info(
                "tts_output: count=%d, avg_interval=%d, length=%d, chat_id=%s,"
                " data_index=%d"
                % (
                    self._tts_output_stats.count,
                    (curr_time - self._tts_output_stats.prev_time)
                    / self._tts_output_stats.log_count_period,
                    len(data),
                    chat_id,
                    data_index,
                ),
            )
            self._tts_output_stats.prev_time = curr_time
        self._tts_output_stats.count += 1

        self._tts_audio_queue.put((chat_id, data_index, data))
        if self._output_file_dir:
            if data_index == 0:
                file_path = os.path.join(
                    self._output_file_dir,
                    "server_%s.pcm" % chat_id,
                )
                fs = open(file_path, "wb")
                self._output_file_streams[chat_id] = fs
                self._thread_executor.submit(fs.write, data)
            else:
                fs = self._output_file_streams[chat_id]
                self._thread_executor.submit(fs.write, data)

    def _on_tts_complete(self, chat_id: str) -> None:
        logger.info("on_tts_complete: chat_id=%s" % chat_id)
        self._tts_audio_queue.put((chat_id, -1, b""))
        if self._output_file_dir and chat_id in self._output_file_streams:
            self._output_file_streams[chat_id].close()
            self._output_file_streams.pop(chat_id, None)

    def _create_session_started(self):
        resp = ModelstudioVoiceChatResponse(
            event=ModelstudioVoiceChatEvent.SESSION_STARTED,
            payload=ModelstudioVoiceChatSessionStartedPayload(
                session_id=self._session_id,
            ),
        )
        return json.dumps(resp.model_dump(), ensure_ascii=False)

    def _create_session_stopped(self):
        resp = ModelstudioVoiceChatResponse(
            event=ModelstudioVoiceChatEvent.SESSION_STOPPED,
            payload=ModelstudioVoiceChatSessionStoppedPayload(
                session_id=self._session_id,
            ),
        )
        return json.dumps(resp.model_dump(), ensure_ascii=False)

    def _create_audio_transcript(self, text: str, finished: bool):
        resp = ModelstudioVoiceChatResponse(
            event=ModelstudioVoiceChatEvent.AUDIO_TRANSCRIPT,
            payload=ModelstudioVoiceChatAudioTranscriptPayload(
                session_id=self._session_id,
                text=text,
                finished=finished,
            ),
        )
        return json.dumps(resp.model_dump(), ensure_ascii=False)

    def _create_response_text(
        self,
        text: str,
        tool_calls: List[ChoiceDeltaToolCall],
        finished: bool,
    ):
        resp = ModelstudioVoiceChatResponse(
            event=ModelstudioVoiceChatEvent.RESPONSE_TEXT,
            payload=ModelstudioVoiceChatResponseTextPayload(
                session_id=self._session_id,
                text=text,
                tool_calls=tool_calls,
                finished=finished,
            ),
        )
        return json.dumps(resp.model_dump(), ensure_ascii=False)

    @staticmethod
    def convert_chat_completion_chunk_to_messages(
        merged_response: ChatCompletionChunk,
        user_text: str,
    ) -> list[OpenAIMessage]:
        """Convert ChatCompletionChunk to a list of OpenAIMessage objects.

        Args:
            merged_response: The merged ChatCompletionChunk response
            user_text: The original user input text

        Returns:
            List of OpenAIMessage containing user and assistant messages
        """
        messages = []

        # Add user message
        user_message = UserMessage(content=user_text)
        messages.append(user_message)

        # Add assistant message
        if merged_response and merged_response.choices:
            choice = merged_response.choices[0]
            if choice.delta:
                assistant_message = AssistantMessage(
                    content=choice.delta.content or "",
                    tool_calls=choice.delta.tool_calls,
                )
                messages.append(assistant_message)

        return messages

    def _chat_llm(
        self,
        query: str,
        chat_id: str,
    ) -> Tuple[str, Stream[ChatCompletionChunk]]:
        if self._tools:
            model = "qwen-plus"
        else:
            model = "qwen-turbo-latest"

        historical_messages = self._chat_store.get_messages(self._session_id)

        return TextChatFlow.chat(
            model=model,
            query=query,
            chat_id=chat_id,
            history=historical_messages,
            tools=self._tools,
        )

    def _chat_rag_with_llm(self, query: str, chat_id: str):
        future = self._async_executor.submit(
            self._async_chat_rag_with_llm,
            query,
        )
        responses = future.result()
        print(f"future responses: {responses}")
        return chat_id, responses

    async def _async_chat_rag_with_llm(
        self,
        query: str,
    ):
        rag_component = ModelstudioRag()
        llm = BaseLLM()
        messages = [
            {
                "role": "system",
                "content": """
        你是一个智能助手。
        # Knowledge base
        请记住以下材料，他们可能对回答问题有帮助。
        ${documents}
        """,
            },
            {"role": "user", "content": query},
        ]
        rag_input = RagInput(
            messages=messages,
            workspace_id=self._parameters.modelstudio_kb.workspace_id,
            rag_options={
                "pipeline_ids": self._parameters.modelstudio_kb.index_ids,
            },
            rest_token=1000,
        )
        try:
            # Run RAG component asynchronously
            rag_output = await rag_component.arun(rag_input)

            # Output results
            print("RAG Result:", rag_output.rag_result)
            print("Updated Messages:")
            chunks = llm.astream(
                model="qwen-max",
                messages=rag_output.messages,
            )
            print(f"chunks: {chunks}")
            return chunks
        except Exception as e:
            print("Error during RAG execution:", e)

    def _load_tools(self, tools_dir: str) -> List[dict]:
        """
        Dynamically load tool definitions from all JSON files

        Args:
            tools_dir: Path to the tools directory

        Returns:
            List of merged tools
        """
        all_tools = []

        if not os.path.exists(tools_dir):
            logger.warning(f"tools directory does not exist: {tools_dir}")
            return all_tools

        # Iterate through all JSON files in the tools directory
        for filename in os.listdir(tools_dir):
            if filename.endswith(".json"):
                file_path = os.path.join(tools_dir, filename)
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        tools_data = json.load(f)
                        if isinstance(tools_data, list):
                            all_tools.extend(tools_data)
                        else:
                            all_tools.append(tools_data)
                    logger.info(f"load tools from: {filename}")
                except Exception as e:
                    logger.error(f"failed to load tools from {filename}: {e}")

        logger.info(f"total loaded tools: {len(all_tools)}")
        return all_tools


server = FastApiWebsocketServer(
    endpoint_path="/api",
    service_class=VoiceChatService,
)

if __name__ == "__main__":
    server.run()

# call the service with
"""
export PYTHONPATH=$(pwd):$PYTHONPATH
python demos/voice_chat/backend/app.py
"""
