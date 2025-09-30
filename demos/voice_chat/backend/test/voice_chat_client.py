# -*- coding: utf-8 -*-
import base64
import json
import logging
import os
import threading
import time
import uuid
from logging.handlers import TimedRotatingFileHandler
from typing import Optional, List
from concurrent.futures.thread import ThreadPoolExecutor

try:
    import pyaudio
except ImportError:
    print("ImportError: Please install pyaudio by `pip install pyaudio`")

import websocket

g_vendor = "azure"  # modelstudio, azure

g_input_files = ["./chat.pcm"]

g_output_dir = os.path.expanduser(
    os.environ.get("OUTPUT_FILE_DIR", "~/Downloads/"),
)


def get_logger(
    name: str,
    enable_console: bool = True,
    filename: Optional[str] = None,
):
    logger = logging.getLogger(name)
    logger.setLevel(level=logging.INFO)

    logger.handlers = get_logging_handlers(enable_console, filename)
    logger.propagate = False
    return logger


def get_logging_handlers(enable_console: bool, filename: str):
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(process)d - %(lineno)d- %(levelname)s - %(message)s",  # noqa
    )

    logging_handlers = []
    if filename is not None:
        log_rotate_handler = TimedRotatingFileHandler(
            filename=filename,
            when="midnight",
            interval=1,
            backupCount=7,
        )
        log_rotate_handler.suffix = "%Y-%m-%d.log"
        log_rotate_handler.setLevel(logging.DEBUG)
        log_rotate_handler.setFormatter(formatter)
        logging_handlers.append(log_rotate_handler)

    if enable_console is True:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.DEBUG)
        console_handler.setFormatter(formatter)
        logging_handlers.append(console_handler)

    return logging_handlers


def create_session_start_req(request_id: str) -> str:
    request = {
        "directive": "SessionStart",
        "payload": {
            "upstream": {
                # "asr_vendor": g_vendor,
                # "asr_options": {
                #     "language": "zh-CN"
                # }
            },
            "downstream": {
                # "tts_vendor": g_vendor,
                # "tts_options": {
                #     "voice": "longcheng_v2",
                # }
            },
            "parameters": {
                "enable_tool_call": True,
                # "modelstudio_kb": {
                #     "api_key": os.environ.get("DASHSCOPE_API_KEY"),
                #     "workspace_id": "llm-czal8nvvwb8d47ks",
                #     "index_ids": ["dxau0m7a5j", "opsatpu3ct"],
                # },
            },
        },
    }

    return json.dumps(request, ensure_ascii=False)


def create_session_stop_req(request_id: str) -> str:
    request = {
        "directive": "SessionStop",
        "payload": {},
    }

    return json.dumps(request, ensure_ascii=False)


class VoiceChatClient:

    def __init__(self, file_list: List[str]):
        headers = {
            "Authorization": "Bearer %s" % os.environ.get("DASHSCOPE_API_KEY"),
            "user-agent": "qwenos/0.1.0.; python/3.8.19; platform/macOS-14.4.1-arm64-arm-64bit; processor/arm",  # noqa
        }
        self._file_list = file_list
        self._ws = websocket.WebSocketApp(
            url="ws://127.0.0.1:8000/api",
            header=headers,
            on_open=self.on_open,
            on_message=self.on_message,
            on_error=self.on_error,
            on_close=self.on_close,
        )
        self._request_id = str(uuid.uuid4())
        self._logger = get_logger("client")
        self._condition = threading.Condition()
        self._send_thread = threading.Thread(target=self._send_loop)
        self._running = False
        self._player = pyaudio.PyAudio()
        self._stream = self._player.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=16000,
            output=True,
        )
        self._ended_response_audio_count = 0
        self._output_file_streams = {}
        self._output_round_index = 0
        self._play_thread_executor = ThreadPoolExecutor(max_workers=1)
        self._write_thread_executor = ThreadPoolExecutor(max_workers=1)
        self._tail_audio_request_time = None
        self._first_audio_response_time = None
        self._tool_calls_received = False

    def run(self):
        self._logger.info("======= run begin =======")
        self._running = True
        self._send_thread.start()
        self._ws.run_forever()
        self._logger.info("======= run end =======")

    def stop(self):
        self._logger.info("----- stop begin -----")
        self._running = False
        self._send_thread.join()

        self._play_thread_executor.shutdown()
        self._write_thread_executor.shutdown()
        self._stream.stop_stream()
        self._stream.close()
        self._player.terminate()

        time.sleep(2)
        self._ws.close()
        self._logger.info("----- stop end -----")

    def _send_loop(self):
        with self._condition:
            self._condition.wait()

            self._send_text(create_session_start_req(self._request_id))

            for file_path in self._file_list:
                self._send_file(file_path)

    def _send_file(self, file_path: str):
        packet_duration = 100
        packet_length = int(2 * 16000 * packet_duration / 1000)
        silence_packet = bytes(packet_length)
        silence_tail_packet_num = 5000 / 100

        file_end = False
        packet_count = 0
        silence_tail_packet_count = 0
        start_time = time.time()
        last_packet_time = int(time.time() * 1000)
        with open(file_path, "rb") as file:
            while self._running is True:
                if silence_tail_packet_count >= silence_tail_packet_num:
                    break

                if file_end is True:
                    packet = silence_packet
                    silence_tail_packet_count += 1
                else:
                    packet = file.read(packet_length)
                    if not packet:
                        packet = silence_packet
                        silence_tail_packet_count += 1
                        file_end = True
                        if self._tail_audio_request_time is None:
                            self._tail_audio_request_time = int(
                                time.time() * 1000,
                            )
                        self._logger.info("send last question audio")
                    elif len(packet) < packet_length:
                        packet += silence_packet[len(packet) :]
                        file_end = True
                        if self._tail_audio_request_time is None:
                            self._tail_audio_request_time = int(
                                time.time() * 1000,
                            )
                        self._logger.info("send last question audio")

                curr_packet_time = int(time.time() * 1000)

                self._logger.info(
                    "send_data: size=%d, count=%d, interval=%d"
                    % (
                        len(packet),
                        packet_count,
                        curr_packet_time - last_packet_time,
                    ),
                )

                self._send_data(packet)

                last_packet_time = curr_packet_time
                packet_count += 1
                next_pkt_time = start_time + (
                    packet_count * packet_duration / 1000.0
                )

                sleep_duration = next_pkt_time - time.time()
                if sleep_duration > 0:
                    time.sleep(sleep_duration)

    def _send_text(self, text: str):
        self._logger.info("send_text: %s" % text)
        self._ws.send_text(text)

    def _send_data(self, data: bytes):
        self._ws.send_bytes(data)

    def on_open(self, ws):
        self._logger.info("on_open")
        with self._condition:
            self._condition.notify_all()

    def on_message(self, ws, message):
        if isinstance(message, str):
            self._logger.info("on_message: %s" % message)
            response = json.loads(message)
            event = response.get("event")

            if event == "SessionStarted":
                pass
            elif event == "SessionStopped":
                self.stop()
            elif event == "ResponseAudioStarted":
                if g_output_dir:
                    file_path = os.path.join(
                        g_output_dir,
                        f"client_{self._output_round_index}.pcm",
                    )
                    fs = open(file_path, "wb")
                    self._output_file_streams[self._output_round_index] = fs
            elif event == "ResponseAudioEnded":
                self._ended_response_audio_count += 1
                if self._ended_response_audio_count == len(g_input_files):
                    self._send_text(create_session_stop_req(self._request_id))
                if self._output_round_index in self._output_file_streams:
                    fs = self._output_file_streams[self._output_round_index]
                    fs.close()
                    del self._output_file_streams[self._output_round_index]
                    self._output_round_index += 1
            elif event == "ResponseText":
                payload = response.get("payload")
                content = payload.get("text")
                tool_calls = payload.get("tool_calls")
                if tool_calls:
                    self._tool_calls_received = True
                if content:
                    self._tool_calls_received = False
                finished = payload.get("finished")
                if self._tool_calls_received and finished:
                    self._send_text(create_session_stop_req(self._request_id))
        elif isinstance(message, bytes):
            self._logger.info("on_data: %s" % len(message))
            if self._first_audio_response_time is None:
                self._first_audio_response_time = int(time.time() * 1000)
                self._logger.info(
                    "first_audio_response_delay: %d"
                    % (
                        self._first_audio_response_time
                        - self._tail_audio_request_time
                    ),
                )

            self._play_thread_executor.submit(self._stream.write, message)
            if self._output_round_index in self._output_file_streams:
                fs = self._output_file_streams[self._output_round_index]
                self._write_thread_executor.submit(fs.write, message)

    def on_error(self, ws, error):
        self._logger.info("on_error: %s" % error)
        self._logger.info(error)

    def on_close(self, ws, a, b):
        self._logger.info(f"on_close: {ws}, {a}, {b}")


if __name__ == "__main__":
    client = VoiceChatClient(g_input_files)
    client.run()
