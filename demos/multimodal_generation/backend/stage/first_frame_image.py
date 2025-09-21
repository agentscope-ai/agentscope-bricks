# -*- coding: utf-8 -*-
import asyncio
import re
from typing import AsyncGenerator

from agentscope_bricks.components.generations.qwen_image_edit import (
    QwenImageEditInput,
)

from agentscope_bricks.components.generations.qwen_image_generation import (
    QwenImageGen,
)

from agentscope_bricks.components import (
    ImageGeneration,
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
from demos.multimodal_generation.backend.utils.generation_util import (
    generate_image_t2i,
)


class FirstFrameImageHandler(Handler):
    def __init__(self, stage_session: StageSession):
        super().__init__(stage_session)
        self.config = g_config.get("first_frame_image")
        self.image_edit = ImageEdit()
        self.qwen_image_edit = QwenImageEdit()

    @trace(
        trace_type=TraceType.AGENT_STEP,
        trace_name="first_frame_image",
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
            logger.error("No first frame description message found")
            return

        # Create assistant message
        assistant_message = Message(
            role=Role.ASSISTANT,
        )

        # Generate images in parallel for all first frame descriptions
        image_tasks = []
        # script_message = self.stage_session.get_stage_message(Stage.SCRIPT)
        # product_image_url = (
        #     script_message.content[0].data.get("image_url")
        #     if script_message
        #     else None
        # )
        ti2_model = self.config.get("t2i_model")
        for i, content in enumerate(first_frame_desc_message.content):
            # if product_image_url:
            #     task = self._i2i_generate_single_image(
            #         content.text,
            #         product_image_url,
            #     )
            # else:
            # Use text-to-image generation
            task = generate_image_t2i(ti2_model, content.text)
            image_tasks.append(task)

        rps = self.config.get("rps", 1)
        task_results = []
        for i in range(0, len(image_tasks), rps):
            batch_tasks = image_tasks[i : i + rps]
            batch_results = await asyncio.gather(*batch_tasks)
            task_results.extend(batch_results)

        image_urls = task_results

        if len(image_urls) != len(first_frame_desc_message.content):
            logger.error(
                f"Number of generated images ({len(image_urls)}) not equals to"
                f" number of first frame desc"
                f" ({len(first_frame_desc_message.content)})",
            )
            return

        # Create mixed content: description and image URL pairs
        mixed_contents = []
        for i, (content, url) in enumerate(
            zip(first_frame_desc_message.content, image_urls),
        ):
            # Add description content
            desc_content = TextContent(
                text=content.text,
            )
            mixed_contents.append(desc_content)

            # Add image content if URL is available
            if url:
                image_content = ImageContent(
                    image_url=url,
                )
                mixed_contents.append(image_content)

        # Update message with final content and status
        assistant_message.content = mixed_contents

        # Yield the completed message
        yield assistant_message.completed()

        # Set stage messages
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
                logger.error(f"Failed to generate image for prompt: {prompt}")
                return ""
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
                logger.error(f"Failed to generate image for prompt: {prompt}")
                return ""


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
