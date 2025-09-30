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

from agentscope_bricks.components import ImageToVideo
from agentscope_bricks.components.generations.image_to_video import (
    ImageToVideoInput,
)
from agentscope_bricks.utils.tracing_utils import trace, TraceType
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
from demos.multimodal_generation.backend.utils.task_util import batch_run_tasks


class VideoHandler(Handler):
    def __init__(self, stage_session: StageSession):
        super().__init__(stage_session)
        self.config = g_config.get("video")
        self.video_gen = ImageToVideo()

    @trace(
        trace_type=TraceType.AGENT_STEP,
        trace_name="video_stage",
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
            raise ValueError("No video description message found")

        # Get first frame images from stage session
        first_frame_image_message = self.stage_session.get_stage_message(
            Stage.FIRST_FRAME_IMAGE,
        )
        if (
            not first_frame_image_message
            or not first_frame_image_message.content
        ):
            raise ValueError("No first frame image message found")

        # Create assistant message
        assistant_message = Message(
            role=Role.ASSISTANT,
        )

        # Calculate the number of available images (every other content item)
        available_images = len(first_frame_image_message.content) // 2

        # Generate videos using batch_run_tasks for streaming results
        rps = self.config.get("rps", 1)

        # Create coroutines with index for batch processing
        coro_list = []
        for i, content in enumerate(video_desc_message.content):
            # Get corresponding first frame image
            if i < available_images:
                image_content = first_frame_image_message.content[i * 2 + 1]
                if (
                    hasattr(image_content, "image_url")
                    and image_content.image_url
                ):
                    coro = self._generate_single_video(
                        content.text,
                        image_content.image_url,
                        index=i,
                    )
                else:
                    raise ValueError(f"No image URL found for video {i}")
            else:
                raise ValueError(f"No corresponding image found for video {i}")
            coro_list.append(coro)

        # Track completion and yield results as they come
        all_mixed_contents = (
            []
        )  # Keep track of all accumulated content for final result
        completed_count = 0
        total_count = len(video_desc_message.content)

        # Process videos in batches and yield results incrementally
        async for index, video_url in batch_run_tasks(coro_list, rps):
            completed_count += 1

            # Get the corresponding content for this index
            content = video_desc_message.content[index]

            # Create incremental mixed content for this video
            incremental_contents = []

            # Add description content
            desc_content = TextContent(
                text=content.text,
                index=index,
            )
            incremental_contents.append(desc_content)

            # Add video content using DataContent if URL is available
            if video_url:
                video_content = DataContent(
                    data={video_url: content.text},
                    index=index,
                )
                incremental_contents.append(video_content)

            # Also keep track for final accumulated result
            all_mixed_contents.extend(incremental_contents)

            # Create partial message with incremental content
            partial_message = Message(role=Role.ASSISTANT)
            partial_message.content = incremental_contents

            # Yield the incremental result
            if completed_count == total_count:
                # Final result - mark as completed
                yield partial_message.completed()
            else:
                # Intermediate result - don't mark as completed yet
                yield partial_message

        # Verify all videos were generated
        if completed_count != total_count:
            raise RuntimeError(
                f"Number of generated videos ({completed_count}) not equals to"
                f" number of video descriptions ({total_count})",
            )

        # Update assistant message with final content and set stage messages
        assistant_message.content = all_mixed_contents
        self.stage_session.set_stage_message(
            Stage.VIDEO,
            assistant_message,
        )

    @trace(trace_type=TraceType.AIGC, trace_name="video_generation")
    async def _generate_single_video(
        self,
        prompt: str,
        image_url: str,
        index: int = None,
    ) -> tuple[int, str] | str:
        """
        Generate a single video based on the given prompt and image

        Args:
            prompt: Text description for video generation
            image_url: URL of the first frame image
            index: Optional index to be returned with the result

        Returns:
            If index is provided: tuple of (index, Generated video URL)
            If index is None: Generated video URL (for backward compatibility)
        """
        try:
            model_name = self.config.get("model", "wan2.2-i2v-plus")
            video_gen_input = ImageToVideoInput(
                image_url=image_url,
                prompt=prompt,
                resolution="1080P",
                **{"model_name": model_name},
            )
            result = await self.video_gen.arun(
                video_gen_input,
                **{"watermark": False},
            )

            if not result.video_url:
                raise RuntimeError(f"Failed to generate video: {result}")

            video_url = result.video_url
            return (index, video_url) if index is not None else video_url

        except Exception as e:
            raise RuntimeError(f"Error generating video: {e}")


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
