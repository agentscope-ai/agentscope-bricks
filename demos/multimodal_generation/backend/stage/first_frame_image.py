# -*- coding: utf-8 -*-
import asyncio
import re
from typing import AsyncGenerator

from agentscope_bricks.components.generations.qwen_image_edit import (
    QwenImageEditInput,
)
from agentscope_bricks.components import (
    ImageEdit,
    QwenImageEdit,
)
from agentscope_bricks.components.generations.image_edit import (
    ImageGenInput as ImageEditInput,
)
from agentscope_runtime.engine.schemas.agent_schemas import (
    Message,
    TextContent,
    ImageContent,
    Role,
    Content,
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
from demos.multimodal_generation.backend.utils.generation_util import (
    generate_image_t2i,
)
from demos.multimodal_generation.backend.utils.task_util import batch_run_tasks


class FirstFrameImageHandler(Handler):
    def __init__(self, stage_session: StageSession):
        super().__init__(stage_session)
        self.config = g_config.get("first_frame_image")
        self.image_edit = ImageEdit()
        self.qwen_image_edit = QwenImageEdit()

    @trace(
        trace_type=TraceType.AGENT_STEP,
        trace_name="first_frame_image_stage",
        get_finish_reason_func=get_agent_message_finish_reason,
        merge_output_func=merge_agent_message,
    )
    async def handle(
        self,
        input_message: Message,
    ) -> AsyncGenerator[Message | Content, None]:
        """
        Asynchronously generate first frame images based on first frame
        descriptions and role images

        Returns:
            Generated first frame images output
        """
        # Get first frame description message from stage session
        first_frame_desc_message = self.stage_session.get_stage_message(
            Stage.FIRST_FRAME_DESCRIPTION,
        )
        if (
            not first_frame_desc_message
            or not first_frame_desc_message.content
        ):
            raise ValueError("No first frame description message found")

        # Create assistant message
        assistant_message = Message(
            role=Role.ASSISTANT,
        )

        # Generate images using batch_run_tasks for streaming results
        ti2_model = self.config.get("t2i_model")
        rps = self.config.get("rps", 1)

        # Create coroutines with index for batch processing
        coro_list = []
        for i, content in enumerate(first_frame_desc_message.content):
            coro = generate_image_t2i(ti2_model, content.text, index=i)
            coro_list.append(coro)

        # Track completion and yield results as they come
        all_mixed_contents = (
            []
        )  # Keep track of all accumulated content for final result
        completed_count = 0
        total_count = len(first_frame_desc_message.content)

        # Process images in batches and yield results incrementally
        async for index, image_url in batch_run_tasks(coro_list, rps):
            completed_count += 1

            # Get the corresponding content for this index
            content = first_frame_desc_message.content[index]

            # Create incremental mixed content for this frame
            incremental_contents = []

            # Add description content
            desc_content = TextContent(
                text=content.text,
                index=index,
            )
            incremental_contents.append(desc_content)

            # Add image content if URL is available
            if image_url:
                image_content = ImageContent(
                    image_url=image_url,
                    index=index,
                )
                incremental_contents.append(image_content)

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

        # Verify all images were generated
        if completed_count != total_count:
            raise RuntimeError(
                f"Number of generated images ({completed_count}) not equals to"
                f" number of first frame desc ({total_count})",
            )

        # Update assistant message with final content and set stage messages
        assistant_message.content = all_mixed_contents
        self.stage_session.set_stage_message(
            Stage.FIRST_FRAME_IMAGE,
            assistant_message,
        )

    async def _i2i_generate_single_image(
        self,
        prompt: str,
        base_image_url: str,
    ) -> str:
        """
        Generate a single image based on the given prompt and base image

        Args:
            prompt: Text description for image generation
            base_image_url: URL of the base image

        Returns:
            Generated image URL
        """

        model_name = self.config.get("i2i_model", "wanx2.1-imageedit")

        if model_name.startswith("qwen"):
            image_edit_input = QwenImageEditInput(
                image_url=base_image_url,
                prompt=prompt,
            )
            image_edit_output = await self.qwen_image_edit.arun(
                image_edit_input,
                model_name=model_name,
                **{"watermark": False},
            )
            if image_edit_output.results:
                return image_edit_output.results[0]
            else:
                raise RuntimeError(
                    f"Failed to generate image for prompt: {prompt}",
                )
        else:
            image_edit_input = ImageEditInput(
                function="remove_watermark",
                base_image_url=base_image_url,
                prompt=prompt,
            )

            image_edit_output = await self.image_edit.arun(
                image_edit_input,
                model_name=model_name,
                **{"watermark": False},
            )

            if image_edit_output.results:
                return image_edit_output.results[0]
            else:
                raise RuntimeError(
                    f"Failed to generate image for prompt: {prompt}",
                )


if __name__ == "__main__":
    from demos.multimodal_generation.backend.test.utils import (
        test_handler,
        mock_stage_session,
    )

    stage_session = mock_stage_session(stage=Stage.FIRST_FRAME_IMAGE)

    first_frame_description = stage_session.get_first_frame_description()

    message = Message(
        role=Role.USER,
        content=[TextContent(text=first_frame_description)],
    )

    asyncio.run(test_handler(FirstFrameImageHandler, message, stage_session))
