# -*- coding: utf-8 -*-
import json
import os
import time
import threading
from typing import Tuple, List, Optional, Union

from openai import Stream, OpenAI, NOT_GIVEN
from openai.types.chat import ChatCompletionChunk, ChatCompletion

from agentscope_bricks.components.memory.local_memory import MessageT
from agentscope_bricks.constants import BASE_URL, DASHSCOPE_API_KEY
from agentscope_bricks.utils.schemas.oai_llm import (
    UserMessage,
    AssistantMessage,
    OpenAIMessage,
)
from agentscope_bricks.utils.logger_util import logger
from agentscope_bricks.utils.message_util import merge_incremental_chunk
from system_prompt import SYSTEM_PROMPT


def load_tools(tools_dir: str) -> List[dict]:
    """
    Dynamically load tool definitions from all JSON files in the tools
    directory

    Args:
        tools_dir: Path to the tools directory

    Returns:
        Merged list of tools
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


class TextChatFlow:

    def __init__(self):
        """
        Initialize TextChatFlow with thread-local storage for OpenAI
        client instances.
        """
        # Use thread-local storage to ensure each thread has its own
        # OpenAI client instance, avoiding thread-safety issues
        self._thread_local = threading.local()

    def _get_client(self) -> OpenAI:
        """
        Get or create thread-local OpenAI client instance.

        Returns:
            OpenAI client instance for the current thread
        """
        if not hasattr(self._thread_local, "client"):
            # Create client for this thread
            self._thread_local.client = OpenAI(
                api_key=DASHSCOPE_API_KEY,
                base_url=BASE_URL,
            )
            logger.info(
                "Created OpenAI client for thread: %s"
                % threading.current_thread().name,
            )
        return self._thread_local.client

    def chat(
        self,
        model: str,
        query: str,
        chat_id: str,
        history: Optional[List[MessageT]] = [],
        tools: Optional[List[dict]] = [],
        stream: Optional[bool] = True,
    ) -> Tuple[str, Union[Stream[ChatCompletionChunk], ChatCompletion]]:
        """
        Execute chat completion with the given parameters.

        Args:
            model: Model name to use for chat completion
            query: User query text
            chat_id: Unique identifier for this chat session
            history: List of historical messages
            tools: List of tool definitions for function calling
            stream: Whether to stream the response

        Returns:
            Tuple of (chat_id, responses)
        """
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]

        # Convert historical messages to the format expected by OpenAI API
        for msg in history:
            if isinstance(msg, UserMessage):
                messages.append({"role": "user", "content": msg.content})
            elif isinstance(msg, AssistantMessage):
                messages.append({"role": "assistant", "content": msg.content})
            elif isinstance(msg, OpenAIMessage):
                messages.append({"role": msg.role, "content": msg.content})

        # Add current user query
        messages.append({"role": "user", "content": query})

        # Get thread-local client instance
        client = self._get_client()

        responses = client.chat.completions.create(
            model=model,
            messages=messages,
            stream=stream,
            extra_body={"enable_search": True},
            tools=tools if tools else NOT_GIVEN,
        )

        return chat_id, responses


if __name__ == "__main__":
    # Dynamically load all tool files from the tools directory
    tools = load_tools("tools")

    # Test with a query that should trigger set_clock function
    # query = "每周五下午三点半提醒我开会"
    # query = "音量调到60"
    # query = "播放周杰伦的七里香"
    # query = "打电话给小王"
    query = "请帮忙发信息问小王何时方便见面"
    history = [
        UserMessage(content="你好"),
        AssistantMessage(content="你好！有什么可以帮助你的吗？"),
    ]

    # Create TextChatFlow instance
    chat_flow = TextChatFlow()

    stream = True
    logger.info("chat_start"),
    chat_start_time = int(time.time() * 1000)
    chat_id, responses = chat_flow.chat(
        model="qwen-plus",
        query=query,
        chat_id="0",
        history=[],
        tools=tools,
        stream=stream,
    )

    ttft_first_resp = True
    cumulated_responses = []

    if stream is True:
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
                    "chat_ttft: chat_id=%s, ttft=%d"
                    % (chat_id, int(time.time() * 1000) - chat_start_time),
                )
                ttft_first_resp = False

            if (
                response.choices[0].finish_reason
                and response.choices[0].finish_reason != "null"
            ):
                logger.info(
                    "chat_end: chat_id=%s, tail=%d, finish_reason=%s,"
                    " response=%s"
                    % (
                        chat_id,
                        int(time.time() * 1000) - chat_start_time,
                        response.choices[0].finish_reason,
                        json.dumps(response.model_dump(), ensure_ascii=False),
                    ),
                )

            cumulated_responses.append(response)

        merged_response = merge_incremental_chunk(cumulated_responses)
        logger.info(
            "merge response:\n%s"
            % json.dumps(merged_response.model_dump(), ensure_ascii=False),
        )
    else:
        logger.info(
            "chat_end: chat_id=%s, ttft=%d, responses=\n%s"
            % (
                chat_id,
                int(time.time() * 1000) - chat_start_time,
                json.dumps(responses.model_dump(), ensure_ascii=False),
            ),
        )
