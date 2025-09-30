# -*- coding: utf-8 -*-
import time
from typing import Callable, Any, Optional
from concurrent.futures import ThreadPoolExecutor
from agentscope_bricks.components.realtime_clients.azure_tts_client import (
    AzureTtsClient,
    AzureTtsCallbacks,
)
from agentscope_bricks.components.realtime_clients.modelstudio_tts_client import (  # noqa
    ModelstudioTtsClient,
    ModelstudioTtsCallbacks,
)
from agentscope_bricks.utils.schemas.realtime import (
    TtsConfig,
    ModelstudioTtsConfig,
    AzureTtsConfig,
    TtsVendor,
)


class TtsClientPool:
    def __init__(self):
        self.index = 0
        self.clients = []

    def __del__(self):
        self.release()

    def initialize(
        self,
        client_count: int,
        tts_vendor: TtsVendor,
        tts_config: Any,
        tts_callbacks: dict[str, Callable],
    ):
        self.index = 0

        with ThreadPoolExecutor(max_workers=client_count) as executor:
            for i in range(client_count):
                callbacks = AzureTtsCallbacks.model_validate(tts_callbacks)
                client = AzureTtsClient(tts_config, callbacks)
                executor.submit(client.start)
                self.clients.append(client)

    def release(self):
        for client in self.clients:
            client.close()
        self.clients = []

    def get(self, chat_id: Optional[str] = None):
        if not self.clients:
            return

        if not chat_id:
            client = self.clients[self.index]
            self.index = (self.index + 1) % len(self.clients)
            return client

        for client in self.clients:
            if client.config.chat_id == chat_id:
                return client

        self.clients[0].set_chat_id(chat_id)
        return self.clients[0]

    def put(self, chat_id: str):
        if not chat_id or not self.clients:
            return

        for client in self.clients:
            if client.config.chat_id == chat_id:
                client.set_chat_id(None)
                client.async_stop()


class TtsClientFactory:
    """
    Factory class for creating TTS client
    """

    pool: TtsClientPool = None
    vendor: TtsVendor = None
    config: TtsConfig = None
    callbacks: dict[str, Callable] = None

    @staticmethod
    def get_config(tts_vendor: TtsVendor, tts_config: TtsConfig):
        if tts_vendor == TtsVendor.MODELSTUDIO:
            return ModelstudioTtsConfig.model_validate(
                tts_config.model_dump(exclude_unset=True, exclude_none=True),
            )
        elif tts_vendor == TtsVendor.AZURE:
            return AzureTtsConfig.model_validate(
                tts_config.model_dump(exclude_unset=True, exclude_none=True),
            )
        else:
            return None

    @staticmethod
    def create_client(
        tts_vendor: TtsVendor,
        tts_config: Any,
        tts_callbacks: dict[str, Callable],
    ):
        if tts_vendor == TtsVendor.MODELSTUDIO:
            callbacks = ModelstudioTtsCallbacks.model_validate(tts_callbacks)
            return ModelstudioTtsClient(tts_config, callbacks)
        elif tts_vendor == TtsVendor.AZURE:
            client = azure_tts_client_pool.get()
            client.set_chat_id(tts_config.chat_id)
            return client
        else:
            return None

    def get(self, chat_id: str):
        return self.pool.get(chat_id)

    def put(self, chat_id: str):
        self.pool.put(chat_id)

    @staticmethod
    def create_pool(
        client_count: int,
        tts_vendor: TtsVendor,
        tts_config: TtsConfig,
        tts_callbacks: dict[str, Callable],
    ):
        azure_tts_client_pool.initialize(
            client_count,
            tts_vendor,
            tts_config,
            tts_callbacks,
        )


azure_tts_client_pool = TtsClientPool()

if __name__ == "__main__":

    def _on_tts_data(self, data: bytes, chat_id: str, data_index: int):
        pass

    def _on_tts_complete(self, chat_id: str):
        pass

    callbacks = {
        "on_data": _on_tts_data,
        "on_complete": _on_tts_complete,
    }

    print("initialize begin")
    azure_tts_client_pool.initialize(
        2,
        TtsVendor.AZURE,
        AzureTtsConfig(),
        callbacks,
    )
    print("initialize end")
    time.sleep(5)
    print("initialize exist")
