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

_qwen_tts_tones = {
    "Chelsie": "女",
    "Cherry": "女",
    "Ethan": "男",
    "Serena": "男",
    "Dylan": "北京话-男",
    "Jada": "吴语-女",
    "Sunny": "四川话-女",
}

LINE_SYSTEM_PROMPT_TEMPLATE = """
# 角色
你是一位专业的音视频制作配音导演。你的任务是根据用户提供的分镜脚本，为其中的旁白和每个角色分配合适且统一的音色。

# 工作流程
- 分析脚本：深度理解分镜脚本中的角色性格、情绪状态、场景氛围和故事脉络。
- 选择音色：基于你的分析，从下方的【备选音色列表】中，为每个有台词的角色和旁白选择一个最合适的音色ID。
- 保持一致：核心原则是，同一个角色（或旁白）在所有分镜中必须使用同一个音色ID，以确保听感的一致性。不同的角色应有区分度的音色。

# 输出规范
- 严格按格式输出：完全复述每个分镜的【角色】、【画面】和【旁白/台词】原文，不得杜撰或修改。
- 处理所有分镜：必须处理输入中的每一个分镜，包括角色为"无"的分镜。
- 音色分配规则：如果分镜有旁白内容，无论角色是否为"无"，都需要为旁白分配音色。
- 处理无声分镜：如果分镜中没有任何台词或旁白，则该分镜下无需输出音色信息。
- 内容安全：输出内容禁止包含任何不适宜、违禁或色情词汇。
- 台词长度：角色或旁白的单句中文台词不应超过30个字。

# 相关限制
- 输出的分镜数量，与输入的分镜数量，需要严格相等，且一一对应。

# 备选音色列表如下，请根据对应的台词或旁白选择合适的音色ID
{tones}

# 示例输入
分镜1：
角色：小明, 妈妈
画面：清晨厨房，餐桌上摆满食物，小明皱着眉头坐在桌前。
旁白：早餐时间，小明却对食物提不起兴趣。

分镜2：
角色：妈妈
画面：妈妈从冰箱里拿出一瓶百炼橙汁，神秘地展示给小明看。
旁白：妈妈拿出魔法道具——百炼橙汁。

分镜3：
角色：小明, 妈妈
画面：妈妈打开瓶盖，倒了一杯橙汁递给小明，小明接过杯子闻了闻。
旁白：新鲜橙汁的香气让小明眼前一亮。

分镜4：
角色：无
画面：特写镜头，百炼橙汁的透明瓶身和纯净的橙汁，包装简洁大方。
旁白：百炼橙汁，健康生活的选择。

# 示例输出，请按照以下格式返回
分镜1：
角色：小明, 妈妈
画面：清晨厨房，餐桌上摆满食物，小明皱着眉头坐在桌前。
旁白：早餐时间，小明却对食物提不起兴趣。
音色：Chelsie

分镜2：
角色：妈妈
画面：妈妈从冰箱里拿出一瓶百炼橙汁，神秘地展示给小明看。
旁白：妈妈拿出魔法道具——百炼橙汁。
音色：Chelsie

分镜3：
角色：小明, 妈妈
画面：妈妈打开瓶盖，倒了一杯橙汁递给小明，小明接过杯子闻了闻。
旁白：新鲜橙汁的香气让小明眼前一亮。
音色：Chelsie

分镜4：
角色：无
画面：特写镜头，百炼橙汁的透明瓶身和纯净的橙汁，包装简洁大方。
旁白：百炼橙汁，健康生活的选择。
音色：Chelsie
"""


class LineHandler(Handler):
    def __init__(self, stage_session: StageSession):
        super().__init__(stage_session)
        self.config = g_config.get("line")
        self.llm = BaseLLM()

    @trace(
        trace_type=TraceType.AGENT_STEP,
        trace_name="line_stage",
        get_finish_reason_func=get_agent_message_finish_reason,
        merge_output_func=merge_agent_message,
    )
    async def handle(
        self,
        input_message: Message,
    ) -> AsyncGenerator[Message | Content, None]:
        """
        Asynchronously run the line task to generate character lines

        Returns:
            Generated line output
        """
        storyboard = self.stage_session.get_storyboard()
        if not storyboard:
            raise ValueError("No storyboard found")

        system_message = OpenAIMessage(
            role="system",
            content=LINE_SYSTEM_PROMPT_TEMPLATE.format(
                tones=LineHandler._format_tones(_qwen_tts_tones),
            ),
        )

        user_message = OpenAIMessage(
            role="user",
            content=storyboard,
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
        self.stage_session.set_line(output_message)

    @staticmethod
    def _format_tones(tones: dict):
        """Format tone dictionary into readable text"""
        formatted_lines = []
        for tone_id, description in tones.items():
            formatted_lines.append(f"ID: {tone_id}, 描述： {description}")
        return "\n".join(formatted_lines)


if __name__ == "__main__":
    import asyncio
    from demos.multimodal_generation.backend.test.utils import (
        test_handler,
        mock_stage_session,
    )

    stage_session = mock_stage_session(stage=Stage.LINE)

    storyboard = stage_session.get_storyboard()

    message = Message(
        role=Role.USER,
        content=[TextContent(text=storyboard)],
    )

    asyncio.run(test_handler(LineHandler, message, stage_session))
