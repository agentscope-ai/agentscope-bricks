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


VIDEO_DESCRIPTION_SYSTEM_PROMPT = OpenAIMessage(
    role="system",
    content="""
# 角色
你是一位顶级的电商广告视频描述词生成专家。你将根据用户提供的剧本、分镜、角色描述信息，以及各分镜里的首帧描述中关于场景初始状态以及后续变化的信息，用于指导后续的视频生成。

# 任务描述与要求
- 深刻理解产品卖点，将卖点融入到视觉描述中。你的描述应聚焦于如何通过画面展现产品的优势、质感、使用体验和给用户带来的价值。
- 以镜头语言（如特写、中景、远景、推拉摇移）、主体（模特、产品）、动作和场景氛围来组织语言，重点突出能展示产品亮点的动态动作和细节。
- 描述词应简洁、生动、富有视觉冲击力，能够精准传达画面信息和情绪。
- 视频序号和分镜序号必须与输入信息一一对应且总数保持一致。
- 请直接从"视频1"开始，不要有任何开场白或额外解释。

# 相关限制
- 不能出现少儿不宜、擦边、违禁、色情、夸大或虚假宣传的词汇。
- 不能出现引导用户与未成年人互动的语句。
- 不能询问或泄露用户隐私及敏感信息。
- 不要直接输出广告文案或角色台词，专注于画面描述。

# 示例输出按照以下格式回答：
视频1：
描述：特写，一只干净的手，将一滴晶莹剔透的精华液挤在指尖上，精华液质地清晰可见。

视频2：
描述：中景，一位年轻男士，穿着新款运动鞋，在城市街道上轻快地慢跑，脚步落地时鞋底的缓冲效果有特写展示。

视频3：
描述：场景切换，从嘈杂的地铁车厢，切换到安静的个人世界，女士，戴上耳机，面露享受与宁静的表情，背景中的嘈杂人群变得模糊虚化。

视频4：
描述：快速剪辑，近景，料理机，快速将坚果打成粉末，接着，将水果和蔬菜搅拌成细腻的果昔，展示其强劲的马达和多功能刀头。
""",
)


class VideoDescriptionHandler(Handler):
    def __init__(self, stage_session: StageSession):
        super().__init__(stage_session)
        self.config = g_config.get("video_description")
        self.llm = BaseLLM()

    @trace(
        trace_type=TraceType.AGENT_STEP,
        trace_name="video_description_stage",
        get_finish_reason_func=get_agent_message_finish_reason,
        merge_output_func=merge_agent_message,
    )
    async def handle(
        self,
        input_message: Message,
    ) -> AsyncGenerator[Message | Content, None]:
        """
        Asynchronously run the video description task to generate
        video descriptions for each storyboard

        Returns:
            Generated video description output
        """
        script = self.stage_session.get_script()
        if not script:
            raise ValueError("No script found")

        storyboard = self.stage_session.get_storyboard()
        if not storyboard:
            raise ValueError("No storyboard found")

        role_description = self.stage_session.get_role_description()
        if not role_description:
            raise ValueError("No role description found")

        first_frame_description = (
            self.stage_session.get_first_frame_description()
        )
        if not first_frame_description:
            raise ValueError("No first frame description found")

        content = (
            script
            + "\n"
            + storyboard
            + "\n"
            + role_description
            + "\n"
            + first_frame_description
        )

        user_message = OpenAIMessage(
            role="user",
            content=content,
        )

        llm_messages = [VIDEO_DESCRIPTION_SYSTEM_PROMPT, user_message]

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
        self.stage_session.set_video_description(output_message)


if __name__ == "__main__":
    import asyncio
    from demos.multimodal_generation.backend.test.utils import (
        test_handler,
        mock_stage_session,
    )

    stage_session = mock_stage_session(stage=Stage.VIDEO_DESCRIPTION)

    message = Message(
        role=Role.USER,
        content=[TextContent(text="百炼橙汁")],
    )

    asyncio.run(
        test_handler(VideoDescriptionHandler, message, stage_session),
    )
