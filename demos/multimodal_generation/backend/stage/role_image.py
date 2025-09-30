# -*- coding: utf-8 -*-
import asyncio
import re
from typing import AsyncGenerator

from agentscope_runtime.engine.schemas.agent_schemas import (
    Message,
    TextContent,
    DataContent,
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


class RoleImageHandler(Handler):
    def __init__(self, stage_session: StageSession):
        super().__init__(stage_session)
        self.config = g_config.get("role_image")

    @trace(
        trace_type=TraceType.AGENT_STEP,
        trace_name="role_image_stage",
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
            raise ValueError("No role description message found")

        # Create assistant message
        assistant_message = Message(
            role=Role.ASSISTANT,
        )

        _, topic_image = self.stage_session.get_topic()
        if topic_image:
            # TODO(zhiyi): support more images
            image_urls = [topic_image]
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
        else:
            # Generate images using batch_run_tasks for streaming results
            model_name = self.config.get("model")
            rps = self.config.get("rps", 1)

            # Create coroutines with index for batch processing
            coro_list = []
            for i, content in enumerate(role_desc_message.content):
                coro = generate_image_t2i(model_name, content.text, index=i)
                coro_list.append(coro)

            # Track completion and yield results as they come
            all_data = (
                {}
            )  # Keep track of all accumulated data for final result
            completed_count = 0
            total_count = len(role_desc_message.content)

            # Process images in batches and yield results incrementally
            async for index, image_url in batch_run_tasks(coro_list, rps):
                completed_count += 1

                # Get the corresponding content for this index
                content = role_desc_message.content[index]
                if content and image_url:
                    role_name = (
                        re.search(r"角色：([^\n]*)", content.text)
                        .group(1)
                        .strip()
                    )
                    all_data[role_name] = image_url

                    # Create incremental message with only the new role data
                    incremental_data = {role_name: image_url}
                    partial_message = Message(role=Role.ASSISTANT)
                    partial_message.content = [
                        DataContent(data=incremental_data, index=index),
                    ]

                    # Yield the incremental result
                    if completed_count == total_count:
                        # Final result - mark as completed
                        yield partial_message.completed()
                    else:
                        # Intermediate result - don't mark as completed yet
                        yield partial_message

            # Verify all images were generated
            if len(all_data) != total_count:
                raise RuntimeError(
                    f"Number of generated images ({len(all_data)}) not"
                    f" equals to number of role desc ({total_count})",
                )

        # Set stage messages with final assistant message
        if not topic_image:
            assistant_message.content = [DataContent(data=all_data)]
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
