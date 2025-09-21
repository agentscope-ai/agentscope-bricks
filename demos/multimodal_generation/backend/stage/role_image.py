# -*- coding: utf-8 -*-
import asyncio
import re
from typing import AsyncGenerator

from agentscope_bricks.components import ImageGeneration
from agentscope_bricks.components.generations.image_generation import (
    ImageGenInput,
)
from agentscope_runtime.engine.schemas.agent_schemas import (
    Message,
    TextContent,
    DataContent,
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


class RoleImageHandler(Handler):
    def __init__(self, stage_session: StageSession):
        super().__init__(stage_session)
        self.config = g_config.get("role_image")

    @trace(
        trace_type=TraceType.AGENT_STEP,
        trace_name="role_image",
        get_finish_reason_func=get_agent_message_finish_reason,
        merge_output_func=merge_agent_message,
    )
    async def handle(
        self,
        input_message: Message,
    ) -> AsyncGenerator[Message | Content, None]:
        """
        Asynchronously generate role images based on role descriptions

        Returns:
            Generated role images output
        """
        # Get role description message from stage session
        role_desc_message = self.stage_session.get_stage_message(
            Stage.ROLE_DESCRIPTION,
        )
        if not role_desc_message or not role_desc_message.content:
            logger.error("No role description message found")
            return

        # Create assistant message
        assistant_message = Message(
            role=Role.ASSISTANT,
        )

        _, topic_image = self.stage_session.get_topic()
        if topic_image:
            # TODO(zhiyi): support more images
            image_urls = [topic_image]
        else:
            # Generate images in parallel for all role descriptions
            model_name = self.config.get("model")
            image_tasks = []
            for content in role_desc_message.content:
                task = generate_image_t2i(model_name, content.text)
                image_tasks.append(task)

            rps = self.config.get("rps", 1)
            task_results = []
            for i in range(0, len(image_tasks), rps):
                batch_tasks = image_tasks[i : i + rps]
                batch_results = await asyncio.gather(*batch_tasks)
                task_results.extend(batch_results)

            image_urls = task_results

            if len(image_urls) != len(role_desc_message.content):
                logger.error(
                    f"Number of generated images ({len(image_urls)}) not"
                    f" equals to number of role desc"
                    f" ({len(role_desc_message.content)})",
                )
                return

        # Create mixed content: description and image URL pairs
        data = {}
        for i, (content, url) in enumerate(
            zip(role_desc_message.content, image_urls),
        ):
            if not content or not url:
                continue

            role_name = (
                re.search(r"角色：([^\n]*)", content.text).group(1).strip()
            )
            data[role_name] = url

        # Update message with final content and status
        assistant_message.content = [DataContent(data=data)]

        # Yield the completed message
        yield assistant_message.completed()

        # Set stage messages
        self.stage_session.set_stage_message(
            Stage.ROLE_IMAGE,
            assistant_message,
        )


if __name__ == "__main__":
    from demos.multimodal_generation.backend.test.utils import (
        test_handler,
        mock_stage_session,
    )

    stage_session = mock_stage_session(stage=Stage.ROLE_IMAGE)

    role_description = stage_session.get_role_description()

    message = Message(
        role=Role.USER,
        content=[TextContent(text=role_description)],
    )

    asyncio.run(test_handler(RoleImageHandler, message, stage_session))
