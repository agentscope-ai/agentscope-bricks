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


FIRST_FRAME_DESCRIPTION_SYSTEM_PROMPT = OpenAIMessage(
    role="system",
    content="""
# 角色
你是一个电商广告短视频自动生成器的其中一个步骤，你的任务是根据对话记录中的广告剧本内容、分镜和角色描述信息，生成与之对应的首帧视频画面描述。

# 任务描述与要求
- 风格：现代简约风格，色彩鲜艳，商业摄影质感，高清画质。
- 每个分镜的首帧描述要简洁明了，突出产品亮点，字数不超过200字。
- 每个分镜的描述中必须包含场景信息。
- 每个分镜的描述中出现的角色名称，必须与输入的角色描名称一致。。
- 输出的分镜数量需要和输入的分镜内容中的分镜数量严格保持一致。


# 相关限制
- 严格按照要求进行优化，禁止修改角色和产品描述信息。
- 模特的服饰信息需要根据其所在的场景进行调整，但需要保持和谐。
- 严禁修改风格。
- 确保画面描述符合动作描述，能够突出产品特点，并保障有当前分镜中必须存在的道具。
- 确保画面描述符合现代简约风格、商业摄影质感和4K高清画质的特点。
- 不能出现少儿不宜、擦边、违禁、色情的词汇。
- 不能回复与消费者有接触的语句。
- 不能询问收货地址等敏感信息。

# 参考示例，示例输出按照以下格式回答：
分镜1：
角色：丽莎
首帧描述：现代简约风格，在明亮的卧室里，一位长发微卷、妆容精致的年轻都市女性丽莎穿着舒适的米色针织衫，睡眼惺忪地在床上寻找手机，表情烦躁，色彩鲜艳，商业摄影质感，4K高清画质。

分镜2：
角色：丽莎, 智音魔盒
首帧描述：现代简约风格，卧室床头柜特写，丽莎正对一个深灰色织物材质、立方体形状的智音魔盒说话，音箱顶部的环形呼吸灯正亮起，充满科技感，色彩鲜艳，商业摄影质感，4K高清画质。

分镜3：
角色：丽莎
首帧描述：现代简约风格，阳光透过窗户洒满卧室，穿着舒适米色针织衫的丽莎面带微笑地伸着懒腰，享受着智能生活带来的便捷和愉悦，色彩鲜艳，商业摄影质感，4K高清画质。
""",  # noqa
)


class FirstFrameDescriptionHandler(Handler):
    def __init__(self, stage_session: StageSession):
        super().__init__(stage_session)
        self.config = g_config.get("first_frame_description")
        self.llm = BaseLLM()

    @trace(
        trace_type=TraceType.AGENT_STEP,
        trace_name="first_frame_description",
        get_finish_reason_func=get_agent_message_finish_reason,
        merge_output_func=merge_agent_message,
    )
    async def handle(
        self,
        input_message: Message,
    ) -> AsyncGenerator[Message | Content, None]:
        """
        Asynchronously run the first frame description task to generate
        first frame descriptions for each storyboard

        Returns:
            Generated first frame description output
        """
        script = self.stage_session.get_script()
        if not script:
            logger.error("No script found")
            return

        storyboard = self.stage_session.get_storyboard()
        if not storyboard:
            logger.error("No storyboard found")
            return

        role_description = self.stage_session.get_role_description()
        if not role_description:
            logger.error("No role description found")
            return

        content = script + "\n" + storyboard + "\n" + role_description

        user_message = OpenAIMessage(
            role="user",
            content=content,
        )

        llm_messages = [FIRST_FRAME_DESCRIPTION_SYSTEM_PROMPT, user_message]

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
        self.stage_session.set_first_frame_description(output_message)


if __name__ == "__main__":
    import asyncio
    from demos.multimodal_generation.backend.test.utils import (
        test_handler,
        mock_stage_session,
    )

    stage_session = mock_stage_session(stage=Stage.FIRST_FRAME_DESCRIPTION)

    role_description = stage_session.get_role_description()

    message = Message(
        role=Role.USER,
        content=[TextContent(text=role_description)],
    )

    asyncio.run(
        test_handler(FirstFrameDescriptionHandler, message, stage_session),
    )
