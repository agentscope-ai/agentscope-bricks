# -*- coding: utf-8 -*-
from agentscope_bricks.models import BaseLLM
from typing import AsyncGenerator

from agentscope_runtime.engine.schemas.agent_schemas import (
    Message,
    TextContent,
    Role,
    Content,
)
from agentscope_bricks.utils.schemas.oai_llm import OpenAIMessage
from agentscope_bricks.utils.logger_util import logger
from agentscope_bricks.utils.message_util import (
    get_agent_message_finish_reason,
    merge_agent_message,
)
from agentscope_bricks.utils.tracing_utils import trace, TraceType
from demos.multimodal_generation.backend.config import g_config
from demos.multimodal_generation.backend.common.handler import Handler
from demos.multimodal_generation.backend.common.stage_manager import (
    StageSession,
    Stage,
)
from demos.multimodal_generation.backend.utils.message_util import (
    process_response_chunk,
)


ROLE_DESCRIPTION_SYSTEM_PROMPT = OpenAIMessage(
    role="system",
    content="""
# 角色
你是专业的广告角色设计师，你的任务是根据客户提供的产品信息、广告主题和目标人群，设计出符合广告调性的角色形象。
用户可能会要求你生成广告视频，此时你应该生成角色描述，后续步骤会基于你的描述来生成视觉内容。

# 要求
- 整体风格需与产品定位和广告主题保持一致（例如：写实、卡通、时尚、科技感等），并具备高品质的视觉效果。
- 每个角色的描述需简洁明了，不超过30个字，包含气质、面部特征、发型等关键信息。
- 每个角色都需要描述具体的服饰细节和所处的场景（需与产品使用场景相关）。
- 角色数量：1-4。
- 直接以“角色1”开始，不需要先铺垫其他内容。

# 相关限制
- 不能出现不适宜、违禁、色情的词汇。
- 不能与用户进行角色扮演式的互动。
- 不能询问个人敏感信息。

# 输出示例按照以下格式回答（角色数量介于1-4之间，如果只有1个角色，只需要写角色1即可。）：
角色1：
角色：都市白领
角色描述：气质干练，面部轮廓清晰，利落的及肩短发。服饰：白色丝质衬衫与米色高腰西裤（明亮的办公室）。
角色2：
角色：健身达人
角色描述：阳光活力，小麦肤色，眼神坚定，扎着高马尾。服饰：荧光色运动背心与黑色紧身裤（健身房）。
角色3：
角色：精致妈妈
角色描述：气质温柔，面带微笑，有亲和力，长卷发盘起。服饰：浅蓝色针织开衫与白色连衣裙（温馨的客厅）。
""",  # noqa
)


class RoleDescriptionHandler(Handler):
    def __init__(self, stage_session: StageSession):
        super().__init__(stage_session)
        self.config = g_config.get("role_description")
        self.llm = BaseLLM()

    @trace(
        trace_type=TraceType.AGENT_STEP,
        trace_name="role_description",
        get_finish_reason_func=get_agent_message_finish_reason,
        merge_output_func=merge_agent_message,
    )
    async def handle(
        self,
        input_message: Message,
    ) -> AsyncGenerator[Message | Content, None]:
        """
        Asynchronously run the role description task to generate character
        descriptions

        Returns:
            Generated role description output
        """
        script = self.stage_session.get_script()
        if not script:
            logger.error("No script found")
            return

        storyboard = self.stage_session.get_storyboard()
        if not storyboard:
            logger.error("No storyboard found")
            return

        content = script + "\n" + storyboard

        user_message = OpenAIMessage(
            role="user",
            content=content,
        )

        llm_messages = [ROLE_DESCRIPTION_SYSTEM_PROMPT, user_message]

        model_name = self.config.get("model")
        cumulated_chunks = []
        content_index = None
        output_message = Message()
        init_event = True

        async for chunk in self.llm.astream(
            model=model_name,
            messages=llm_messages,
        ):
            async for (
                result,
                out_msg,
                init_ev,
                content_idx,
                cumulated,
            ) in process_response_chunk(
                chunk,
                output_message,
                init_event,
                content_index,
                cumulated_chunks,
            ):
                yield result

                output_message = out_msg
                init_event = init_ev
                content_index = content_idx
                cumulated_chunks = cumulated

        # Set stage messages
        self.stage_session.set_role_description(output_message)


if __name__ == "__main__":
    import asyncio
    from demos.multimodal_generation.backend.test.utils import (
        test_handler,
        mock_stage_session,
    )

    stage_session = mock_stage_session(stage=Stage.ROLE_DESCRIPTION)
    storyboard = stage_session.get_storyboard()

    message = Message(
        role=Role.USER,
        content=[TextContent(text=storyboard)],
    )

    asyncio.run(test_handler(RoleDescriptionHandler, message, stage_session))
