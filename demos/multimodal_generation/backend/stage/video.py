# -*- coding: utf-8 -*-
import asyncio
from typing import AsyncGenerator

from agentscope_runtime.engine.schemas.agent_schemas import (
    Message,
    TextContent,
    DataContent,
    Role,
    Content,
)

from agentscope_bricks.components import TextToVideo, ImageToVideo
from agentscope_bricks.components.generations.image_to_video import (
    ImageToVideoInput,
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


class VideoHandler(Handler):
    def __init__(self, stage_session: StageSession):
        super().__init__(stage_session)
        self.config = g_config.get("video")
        self.video_gen = ImageToVideo()

    @trace(
        trace_type=TraceType.AGENT_STEP,
        trace_name="video",
        get_finish_reason_func=get_agent_message_finish_reason,
        merge_output_func=merge_agent_message,
    )
    async def handle(
        self,
        input_message: Message,
    ) -> AsyncGenerator[Message | Content, None]:
        """
        Asynchronously generate videos based on video descriptions and
        first frame images

        Returns:
            Generated video outputs
        """
        # Get video description message from stage session
        video_desc_message = self.stage_session.get_stage_message(
            Stage.VIDEO_DESCRIPTION,
        )
        if not video_desc_message or not video_desc_message.content:
            logger.error("No video description message found")
            return

        # Get first frame images from stage session
        first_frame_image_message = self.stage_session.get_stage_message(
            Stage.FIRST_FRAME_IMAGE,
        )
        if (
            not first_frame_image_message
            or not first_frame_image_message.content
        ):
            logger.error("No first frame image message found")
            return

        # Create assistant message
        assistant_message = Message(
            role=Role.ASSISTANT,
        )

        # Calculate the number of available images (every other content item)
        available_images = len(first_frame_image_message.content) // 2

        # Generate videos in parallel for all video descriptions
        video_tasks = []
        for i, content in enumerate(video_desc_message.content):
            # Get corresponding first frame image
            if i < available_images:
                image_content = first_frame_image_message.content[i * 2 + 1]
                if (
                    hasattr(image_content, "image_url")
                    and image_content.image_url
                ):
                    task = self._generate_single_video(
                        content.text,
                        image_content.image_url,
                    )
                else:
                    logger.error(f"No image URL found for video {i}")

                    async def empty_result():
                        return ""

                    task = empty_result()
            else:
                logger.error(f"No corresponding image found for video {i}")

                async def empty_result():
                    return ""

                task = empty_result()
            video_tasks.append(task)

        rps = self.config.get("rps", 1)
        task_results = []
        for i in range(0, len(video_tasks), rps):
            batch_tasks = video_tasks[i : i + rps]
            batch_results = await asyncio.gather(*batch_tasks)
            task_results.extend(batch_results)

        # Wait for all videos to be generated
        video_urls = task_results

        if len(video_urls) != len(video_desc_message.content):
            logger.error(
                f"Number of generated videos ({len(video_urls)}) not equals to"
                f" number of video descriptions"
                f" ({len(video_desc_message.content)})",
            )
            return

        # Create mixed content: description and video URL pairs
        mixed_contents = []
        for i, (content, url) in enumerate(
            zip(video_desc_message.content, video_urls),
        ):
            # Add description content
            desc_content = TextContent(
                text=content.text,
            )
            mixed_contents.append(desc_content)

            # Add video content using DataContent if URL is available
            if url:
                video_content = DataContent(
                    data={url: content.text},
                )
                mixed_contents.append(video_content)

        # Update message with final content and status
        assistant_message.content = mixed_contents

        # Yield the completed message
        yield assistant_message.completed()

        # Set stage messages
        self.stage_session.set_stage_message(
            Stage.VIDEO,
            assistant_message,
        )

    @trace(trace_type=TraceType.AIGC, trace_name="video_generation")
    async def _generate_single_video(self, prompt: str, image_url: str) -> str:
        """
        Generate a single video based on the given prompt and image

        Args:
            prompt: Text description for video generation
            image_url: URL of the first frame image

        Returns:
            Generated video URL
        """
        try:
            model_name = self.config.get("model", "wan2.2-i2v-plus")
            video_gen_input = ImageToVideoInput(
                image_url=image_url,
                prompt=prompt,
                **{"model_name": model_name},
            )
            result = await self.video_gen.arun(
                video_gen_input,
                **{"watermark": False},
            )

            if not result.video_url:
                logger.error(f"Failed to generate video: {result.message}")
                return ""

            return result.video_url

        except Exception as e:
            logger.error(f"Error generating video: {e}")
            return ""


if __name__ == "__main__":
    from demos.multimodal_generation.backend.test.utils import (
        test_handler,
        mock_stage_session,
    )

    stage_session = mock_stage_session(stage=Stage.VIDEO)

    message = Message(
        role=Role.USER,
        content=[TextContent(text="百炼橙汁")],
    )

    asyncio.run(test_handler(VideoHandler, message, stage_session))
