# -*- coding: utf-8 -*-
from typing import Any
from pydantic import BaseModel

from agentscope_bricks.components.realtime_clients.realtime_component import (
    RealtimeComponent,
    RealtimeType,
)
from agentscope_bricks.utils.schemas.realtime import AsrConfig


class AsrClient(RealtimeComponent):

    def __init__(self, config: AsrConfig, callbacks: BaseModel):
        super().__init__(RealtimeType.ASR, config, callbacks)

    def start(self, **kwargs: Any) -> None:
        pass

    def stop(self, **kwargs: Any) -> None:
        pass

    def close(self, **kwargs: Any) -> None:
        pass

    def send_audio_data(self, data: bytes) -> None:
        pass
