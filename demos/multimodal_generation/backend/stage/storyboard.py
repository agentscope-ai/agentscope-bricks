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

STORYBOARD_SYSTEM_PROMPT_TEMPLATE = """
# 角色
你是专业的广告分镜师，你将根据客户提供的产品信息和广告主题，为电商视频广告生成分镜脚本。

# 任务描述与要求
- 根据产品和广告主题，生成分镜描述。每个分镜必须包含：角色、画面、旁白三个部分。
- 每个分镜均必须与产品或其带来的体验直接相关。
- 旁白（画外音）是对画面的简要陈述或情感升华，而不是角色之间的对话。
- 角色处理规则：如果画面中出现人物，列出具体角色名称；如果画面中没有人物（如产品特写），角色行写"无"。
- 如果画面中出现多个角色，需要分别列出他们的名字或代称（如：男主角，女主角），不要合并。
- 旁白需要生成中文版。
- 每个分镜必须都有旁白。
- 输出内容直接从"分镜1"开始，不需要先铺垫其他内容。
- 每个分镜的内容严格按照下面的示例输出的格式，即包括角色、画面、旁白三个部分，缺一不可。

# 相关限制
- 不要出现过于复杂或负面的情节。
- 分镜数量不超过4个。
- 每个分镜的角色数量不超过3个。
- 依次枚举的角色名称要严格和输入中的角色名称保持一致，禁止合并或修改。
- 中文旁白不超过30个字。
- 角色不能穿着暴露（比如肚兜，比基尼）。
- 不能出现不适宜、违禁、色情的词汇。
- 不能与用户进行角色扮演式的互动。
- 不能询问个人敏感信息。

# 参考示例
# 示例输入：
《橙汁的魔法》
场景： 一个阳光明媚的早晨，小明和妈妈在厨房里准备早餐。
角色：
- 小明：一个活泼好动的小男孩。
- 妈妈：一位细心且充满爱心的母亲。
- 百炼橙汁：一瓶包装精美的橙汁，瓶身透明，可以看到里面鲜艳的橙色果汁。

故事：
（镜头缓缓推进厨房，小明正在餐桌上吃着面包，看起来有些无精打采。）
妈妈（走进厨房，手里拿着一瓶百炼橙汁）：“小明，今天早上有点特别哦！”
小明（抬头看着妈妈，好奇地问）：“什么特别呀，妈妈？”
妈妈（神秘一笑，拿出百炼橙汁）：“看，这是我们的‘活力小太阳’——百炼橙汁！”
小明（眼睛一亮，兴奋地说）：“哇，真的好像一个小太阳！”
（镜头拉远，母子俩在阳光下享受美好的早餐时光，背景音乐轻快愉悦。）

角色：
- 妈妈：细心且充满爱心的母亲。
- 小明：活泼好动的小男孩。
- 百炼橙汁：一瓶包装精美的橙汁。
产品名称： 百炼橙汁
产品描述： 百炼橙汁采用优质鲜橙榨取，瓶身透明，可以看到里面鲜艳的橙色果汁。瓶盖设计方便开启，外包装上印有可爱的橙子图案，整体给人一种清新自然的感觉。每瓶容量适中，便于携带和饮用。
产品标语： 活力小太阳，每天好心情！

## 示例输出按照以下格式回答（角色、画面、旁白分别各占一行）：
分镜1：
角色：年轻白领
画面：清晨办公室，一位年轻白领略显疲惫地坐在电脑前，打了个哈欠。
旁白：工作日的早晨，总是需要一杯咖啡来唤醒。

分镜2：
角色：无
画面：特写镜头，一只手从包里拿出银色的智能便携咖啡机，按下按钮，咖啡液缓缓流入杯中，蒸汽氤氲。
旁白：无需等待，一键萃取，即刻享受你的专属风味。

分镜3：
角色：年轻白领
画面：白领手持咖啡杯，轻嗅香气后满足地喝了一口，脸上露出精神焕发的笑容，望向窗外的阳光。
旁白：随时随地，让醇香灵感伴你左右。

分镜4：
角色：无
画面：产品特写镜头，智能便携咖啡机的精致外观，银色金属质感，现代科技设计。
旁白：科技改变生活，品质成就梦想。
"""  # noqa


class StoryboardHandler(Handler):
    def __init__(self, stage_session: StageSession):
        super().__init__(stage_session)
        self.config = g_config.get("storyboard")
        self.llm = BaseLLM()

    @trace(
        trace_type=TraceType.AGENT_STEP,
        trace_name="storyboard_stage",
        get_finish_reason_func=get_agent_message_finish_reason,
        merge_output_func=merge_agent_message,
    )
    async def handle(
        self,
        input_message: Message,
    ) -> AsyncGenerator[Message | Content, None]:
        """
        Asynchronously run the storyboard task to generate story storyboards

        Returns:
            Generated storyboard output
        """
        script = self.stage_session.get_script()
        if not script:
            raise ValueError("No script found")

        system_message = OpenAIMessage(
            role="system",
            content=STORYBOARD_SYSTEM_PROMPT_TEMPLATE,
        )

        user_message = OpenAIMessage(
            role="user",
            content=script,
        )

        llm_messages = [system_message, user_message]

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
        self.stage_session.set_storyboard(output_message)


if __name__ == "__main__":
    import asyncio
    from demos.multimodal_generation.backend.test.utils import (
        test_handler,
        mock_stage_session,
    )

    stage_session = mock_stage_session(stage=Stage.STORYBOARD)

    script = stage_session.get_script()

    message = Message(
        role=Role.USER,
        content=[TextContent(text=script)],
    )

    asyncio.run(test_handler(StoryboardHandler, message, stage_session))
