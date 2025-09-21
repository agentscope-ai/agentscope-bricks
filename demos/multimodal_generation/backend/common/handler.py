# -*- coding: utf-8 -*-
from typing import AsyncGenerator

from agentscope_runtime.engine.schemas.agent_schemas import Message, Content
from demos.multimodal_generation.backend.common.stage_manager import (
    StageSession,
)


class Handler:
    def __init__(self, stage_session: StageSession):
        self.stage_session = stage_session

    async def handle(
        self,
        input_message: Message,
    ) -> AsyncGenerator[Message | Content, None]:
        raise NotImplementedError
