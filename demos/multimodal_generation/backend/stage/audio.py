# -*- coding: utf-8 -*-
import asyncio
import os
from typing import AsyncGenerator

import dashscope

from agentscope_runtime.engine.schemas.agent_schemas import (
    Message,
    TextContent,
    Role,
    Content,
    DataContent,
)
from agentscope_bricks.utils.tracing_utils import trace, TraceType
from agentscope_bricks.utils.logger_util import logger
from agentscope_bricks.utils.message_util import (
    get_agent_message_finish_reason,
    merge_agent_message,
)

from demos.multimodal_generation.backend.config import g_config
from demos.multimodal_generation.backend.common.handler import Handler
from demos.multimodal_generation.backend.common.stage_manager import (
    StageSession,
    Stage,
)


class AudioHandler(Handler):
    def __init__(self, stage_session: StageSession):
        super().__init__(stage_session)
        self.config = g_config.get("audio")

    @trace(
        trace_type=TraceType.AGENT_STEP,
        trace_name="audio",
        get_finish_reason_func=get_agent_message_finish_reason,
        merge_output_func=merge_agent_message,
    )
    async def handle(
        self,
        input_message: Message,
    ) -> AsyncGenerator[Message | Content, None]:
        """
        Asynchronously generate audio based on line content from stage session

        Returns:
            Generated audio outputs
        """
        # Get line message from stage session
        line_message = self.stage_session.get_stage_message(Stage.LINE)
        if not line_message or not line_message.content:
            logger.error("No line message found")
            return

        # Create assistant message
        assistant_message = Message(
            role=Role.ASSISTANT,
        )

        # Extract text content from line message
        text_contents = [
            content
            for content in line_message.content
            if isinstance(content, TextContent) and content.text
        ]

        if not text_contents:
            logger.error("No text content found in line message")
            return

        # Process content in groups of 3 (role, dialogue, voice)
        audio_tasks = []
        for i in range(0, len(text_contents), 3):
            if i + 2 < len(text_contents):
                # role = text_contents[i].text
                dialogue = text_contents[i + 1].text  # Chinese dialogue
                voice = text_contents[i + 2].text  # Voice tone

                # Generate audio for Chinese dialogue
                task = self._generate_single_audio(dialogue, voice)
                audio_tasks.append(task)
            else:
                logger.warning(f"Incomplete triplet at index {i}")

        # Wait for all audio generation tasks to complete
        audio_urls = await asyncio.gather(*audio_tasks)

        # Create DataContent with URL-text pairs
        data_dict = {}
        for i, (content, url) in enumerate(
            zip(text_contents[1::3], audio_urls),  # Skip role, get dialogue
        ):
            # Store URL as key and text as value
            if url:
                data_dict[url] = content.text

        # Create DataContent with the URL-text mapping
        data_content = DataContent(
            data=data_dict,
        )

        # Update message with final content and status
        assistant_message.content = [data_content]

        # Yield the completed message
        yield assistant_message.completed()

        # Set stage messages
        self.stage_session.set_stage_message(
            Stage.AUDIO,
            assistant_message,
        )

    @trace(trace_type=TraceType.AIGC, trace_name="tts")
    async def _generate_single_audio(self, text: str, voice: str) -> str:
        """
        Generate audio for a single text using TTS

        Args:
            text: Text to synthesize
            voice: Voice tone to use

        Returns:
            Generated audio URL
        """
        try:
            model_name = self.config.get("model", "qwen-tts")
            response = await dashscope.AioMultiModalConversation.call(
                api_key=os.getenv("DASHSCOPE_API_KEY"),
                model=model_name,
                text=text,
                voice=voice,
            )
            audio_url = response.output.audio["url"]
            return audio_url
        except Exception as e:
            logger.error(
                f"Error generating audio for text '{text}' "
                f"with voice '{voice}': {e}",
            )
            return ""


if __name__ == "__main__":
    from demos.multimodal_generation.backend.test.utils import (
        test_handler,
        mock_stage_session,
    )

    stage_session = mock_stage_session(stage=Stage.AUDIO)

    message = Message(
        role=Role.USER,
        content=[TextContent(text="test audio generation")],
    )

    asyncio.run(test_handler(AudioHandler, message, stage_session))
