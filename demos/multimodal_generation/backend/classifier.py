# -*- coding: utf-8 -*-
from typing import Optional

from agentscope_bricks.models import BaseLLM
from agentscope_runtime.engine.schemas.agent_schemas import (
    Message,
    TextContent,
    Role,
)
from agentscope_bricks.utils.schemas.oai_llm import OpenAIMessage
from agentscope_bricks.utils.logger_util import logger
from agentscope_bricks.utils.tracing_utils import trace, TraceType
from agentscope_bricks.utils.message_util import (
    get_agent_message_finish_reason,
    merge_agent_message,
)
from agentscope_runtime.engine.schemas.agent_schemas import (
    Message as RuntimeMessage,
)

from demos.multimodal_generation.backend.common.constants import (
    NEXT_STAGE,
    REPEAT_STAGE,
)
from demos.multimodal_generation.backend.config import g_config
from demos.multimodal_generation.backend.common.handler import Handler
from demos.multimodal_generation.backend.common.stage_manager import (
    StageSession,
    Stage,
    STAGE_ORDER,
)
from demos.multimodal_generation.backend.utils.message_util import (
    get_message_text_content,
)


INTENT_SYSTEM_PROMPT = OpenAIMessage(
    role="system",
    content=f"""# 角色
你是一个分类大师，你将根据客户的输入准确判断其意图。

# 任务描述与要求
1. 进行 3 分类。
2. 分类包括 Script 生成故事脚本，Storyboard 生成故事分镜设计，RoleDescription 生成角色描述信息
3. 3种类别之间有先后顺序，Script -> Storyboard -> RoleDescription
4. 如果用户要求讲一个故事、做优化或闲聊等，返回"Script"，不能添加其他信息。
5. 当且仅当用户要求进行分镜创作时，返回"Storyboard"，不能添加其他信息。
6. 当且仅当用户要求进行角色创作、生成视频时，返回"RoleDescription"，不能添加其他信息。
7. 除了以上情况外，都返回"Script"，不能添加其他信息。

# 相关限制
1. 严格按照规则进行分类输出。
2. 你的回答严格只能返回"Script"、"Storyboard"、"RoleDescription"、
   "{NEXT_STAGE}"、"{REPEAT_STAGE}" 中的唯一一个单词。

# 参考示例
示例 1：
用户：讲一个故事
输出：Script
示例 2：
用户：更丰富一些
输出：Script
示例 3：
用户：换一个故事，新的故事是关于xxx
输出：Script
示例 4:
用户：现在设计分镜
输出：Storyboard
示例 5:
用户：分镜4多加几个任务
输出：Storyboard
示例 6:
用户：开始生成视频
输出：RoleDescription
用户：创作人物角色描述
输出：RoleDescription
示例 7:
用户：下一步
输出：{NEXT_STAGE}
用户：继续吧
输出：{NEXT_STAGE}
示例 8:
用户：重新生成
输出：{REPEAT_STAGE}
用户：再来一遍
输出：{REPEAT_STAGE}
""",
)


class Classifier(Handler):
    def __init__(self, stage_session: StageSession):
        super().__init__(stage_session)
        self.config = g_config.get("intent", {})
        self.llm = BaseLLM()

    @trace(
        trace_type=TraceType.AGENT_STEP,
        trace_name="classifier",
        get_finish_reason_func=get_agent_message_finish_reason,
        merge_output_func=merge_agent_message,
    )
    async def classify(self, input_message: Message) -> Optional[Stage]:
        """
        Asynchronously run the intent classification task to determine the
        next stage

        Returns:
            Generated intent classification result
        """
        if not input_message:
            logger.error("No messages found in request")
            return

        message_type = input_message.type

        output_stage = self._get_stage_from_message_type(message_type)

        if not output_stage:
            if isinstance(input_message, RuntimeMessage):
                text_content = get_message_text_content(input_message)
            else:
                text_content = input_message.get_text_content()

            # Get user input from request
            if not text_content:
                logger.error("No text content found in request")
                raise ValueError("No text content found in request")

            user_message = OpenAIMessage(
                role="user",
                content=text_content,
            )

            llm_messages = [INTENT_SYSTEM_PROMPT, user_message]

            model_name = self.config.get("model")
            chat_resp = await self.llm.arun(
                model=model_name,
                messages=llm_messages,
            )
            output_stage = self._get_stage_from_message_type(
                chat_resp.choices[0].message.content,
            )

        if output_stage:
            output_index = STAGE_ORDER.index(output_stage)
            for i in range(output_index, len(STAGE_ORDER)):
                self.stage_session.delete_stage(STAGE_ORDER[i])

            if output_stage == Stage.TOPIC:
                self.stage_session.set_stage_message(
                    Stage.TOPIC,
                    input_message,
                )
                output_stage = None

        return output_stage

    def _get_stage_from_message_type(
        self,
        message_type: str,
    ) -> Optional[Stage]:
        if message_type in STAGE_ORDER:
            return Stage(message_type)
        elif message_type == NEXT_STAGE:
            return self.stage_session.get_next_stage()
        elif message_type == REPEAT_STAGE:
            return self.stage_session.get_current_stage()
        else:
            return None


if __name__ == "__main__":
    import asyncio
    from test.utils import (
        mock_stage_session,
    )

    stage_session = mock_stage_session(stage=Stage.ROLE_DESCRIPTION)

    classifier = Classifier(
        stage_session=stage_session,
    )

    asyncio.run(
        classifier.classify(
            Message(
                role=Role.USER,
                content=[TextContent(text="百炼橙汁")],
            ),
        ),
    )
