# -*- coding: utf-8 -*-
from typing import AsyncGenerator

from agentscope_bricks.models import BaseLLM

from agentscope_runtime.engine.schemas.agent_schemas import (
    Message,
    TextContent,
    Role,
    Content,
    ImageContent,
    DataContent,
)
from agentscope_bricks.utils.schemas.oai_llm import OpenAIMessage
from agentscope_bricks.utils.logger_util import logger
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
from demos.multimodal_generation.backend.utils.message_util import (
    process_response_chunk,
    parse_script,
)


SCRIPT_SYSTEM_PROMPT_TEMPLATE = """
# 角色
你是一位顶尖的电商广告创意大师和金牌带货编剧，尤其擅长为家庭、母婴及儿童产品创作短剧脚本。你深谙消费者心理，能够将枯燥的产品卖点转化为生动有趣、引人入胜的短剧故事。你的作品能通过引爆情感共鸣或制造趣味冲突，在短时间内牢牢抓住用户眼球，激发其购买欲望，并巧妙地植入产品核心价值。

# 任务描述与要求
- 紧扣产品主题： 故事需围绕核心推广产品展开，通过一个生活化的场景，巧妙展示产品的核心卖点、使用场景或它能解决的用户痛点。
- 情节生动有趣： 故事要有记忆点，可以是一个小冲突、一个有趣的转折或一个温馨的时刻。剧情要能自然引出产品，让产品成为解决问题或提升幸福感的“英雄”。
- 语言口语化、有感染力： 对白要符合短视频和直播的语境，生动、有网感，能快速拉近与消费者的距离。
- 强调重复记忆： 可以在故事中适当加入重复的口号、产品相关的关键词或声音特效（如产品的趣味音效），加深用户印象。
- 明确角色与产品： 故事描述后面需要将出场角色和核心推广产品列举出来，并用一句话广告语或核心卖点来包装。



# 相关限制
- 不要出现过于复杂或脱离现实的情节。
- 故事长度要适中，适合30-60秒的短视频。
- 主角不超过3个，产品也算一个“隐形主角”。
- 不能出现少儿不宜、擦边、违禁、色情的词汇。
- 不能涉及虚假宣传或夸大产品功效
- 必须按照示例输出输出产品名称
- 必须按照示例输出产品描述，根据产品的名称和功能进行详细编写，主要描述产品的外形、颜色、材质、外包装等特征。100字以内。
- 必须按照示例输出产品标语，根据产品特点，简明响亮，富有创意。10字以内。


# 参考示例
## 示例 1：

用户输入/产品: 儿童玩具收纳箱
故事: 妈妈走进房间，看到满地的玩具，头疼地叹气：“天哪，乐乐的玩具王国又‘沦陷’了！” 乐乐正玩得开心，说：“妈妈，玩具太多了，我不知道放哪里。” 妈妈神秘一笑，推出了一个恐龙造型的收纳箱：“别怕，我们请来了‘玩具吞噬兽’！” 乐乐眼睛一亮：“哇！好酷的恐龙！” 妈妈：“它最喜欢吃乱七八糟的玩具啦，快，我们一起喂饱它！” 乐乐开心地把积木、小汽车一个个“喂”进恐龙的大嘴里。妈妈：“玩具吞噬兽，嗷呜一口！” 乐乐跟着喊：“嗷呜一口！” 不一会儿，房间就整洁了。妈妈摸着乐乐的头说：“看，有‘玩具吞噬兽’帮忙，整理房间也变得好玩了吧！”

## 示例 2：
用户输入/产品: 儿童卡通造型餐具
故事: 饭桌上，琪琪对着一盘西兰花直摇头：“我不要吃绿色的小树！” 爸爸拿出一套飞机造型的餐盘和勺子：“琪琪你看，‘美食航班’准备起飞啦！目的地是琪琪的肚子机场！” 爸爸用飞机勺子“装载”了一块西兰花，“呜——飞机乘客（西兰花）已就位，请求起飞！” 琪琪被逗乐了，张开嘴巴：“啊——欢迎来到肚子机场！” 爸爸：“‘美食航班’降落成功！下一位乘客是谁呢？” 琪琪指着胡萝卜说：“该它了！”

## 示例 3：
用户输入/产品: 智能星空投影夜灯
故事: 晚上，小明躺在床上翻来覆去，指着墙上的影子说：“妈妈，我怕那个大怪兽。” 妈妈温柔地抱住他，拿出一个小小的宇航员玩偶，按了一下开关。瞬间，整个天花板变成了璀璨的星空。“别怕，‘星际宇航员’已经开启了太空保护罩，你看，现在整个房间都是我们的宇宙飞船，那些影子都变成小星星啦。” 小明惊喜地看着满屋的星星和星云，不再害怕了，指着一颗流星说：“妈妈快看！” 妈妈：“在‘星际宇航员’的守护下，做个甜甜的太空梦吧。”


# 完整示例输出：
《乱糟糟王国的终结者》

妈妈走进儿童房，看着满地的积木、娃娃和画笔，无奈地扶着额头叹了口气：“哎，乐乐的玩具王国每天都在上演‘灾难大片’啊！” 正在专心搭建积木城堡的乐乐头也不抬地说：“妈妈，我的城堡需要很多‘建筑材料’，它们不能被关起来！”

这时，妈妈像变魔术一样，从门后推出来一个巨大的、有着可爱大嘴巴的蓝色河马造型收纳箱。“国王陛下，您的王国需要一位新伙伴——‘玩具清理大师’河马先生！”

乐乐好奇地停下手里的活，围着“河马先生”转了一圈，发现它的嘴巴可以张得很大。妈妈笑着说：“河马先生肚子饿了，它最喜欢吃的食物就是散落在地上的玩具哦。我们来玩个‘喂食游戏’吧？”

“好呀好呀！”乐乐立刻兴奋起来，抱起一个皮球，大喊一声“河马先生，吃饭啦！”，然后准确地扔进了收纳箱的大嘴里。接下来，积木、画笔、小汽车……乐乐玩得不亦乐乎，不一会儿，地板就变得干干净净。

妈妈竖起大拇指：“哇，在‘玩具清理大师’的帮助下，国王陛下迅速收复了失地！” 乐乐拍拍“河马先生”的肚子，自豪地说：“以后我的玩具，都由它来守护！”

角色： 妈妈，为孩子的玩具收纳问题而头疼。
角色： 乐乐，一个活泼但“不爱整理”的男孩。
产品名称：河马大嘴玩具收纳箱
产品描述：它是一个圆润敦实的河马造型，采用柔和的哑光质感环保材质，安全无棱角。头部是可向上翻开的“大嘴”翻盖，张开后露出超大收纳空间和两颗呆萌的白色门牙。底部隐藏式万向轮设计，让孩子可以轻松推拉移动。
产品标语：大口吃掉杂乱，玩出整洁新习惯！
"""  # noqa


VL_USER_PROMPT = """
按照如下格式，描述图片里的内容，根据实际检测到的角色数量，输出相应的角色描述。

只按照如下示例输出，不要增加其他无关信息。

如下以3个角色为例，示例输出如下：
角色1：
角色：小熊贝贝
角色描述：圆头圆脑，圆圆的眼睛。服饰：蓝色运动服（宽阔的草地上）

角色2：
角色：小兔莉莉
角色描述：长长的耳朵，柔软的白毛。服饰：粉色小裙子（在大海边上）

角色3：
角色：小松鼠奇奇
角色描述：大大的尾巴，明亮的眼睛。服饰：绿色小背心（在沙漠中）
"""  # noqa


class ScriptHandler(Handler):
    def __init__(self, stage_session: StageSession):
        super().__init__(stage_session)
        self.config = g_config.get("script")
        self.llm = BaseLLM()

    @trace(
        trace_type=TraceType.AGENT_STEP,
        trace_name="script_stage",
        get_finish_reason_func=get_agent_message_finish_reason,
        merge_output_func=merge_agent_message,
    )
    async def handle(
        self,
        input_message: Message,
    ) -> AsyncGenerator[Message | Content, None]:
        """
        Asynchronously run the script task to generate story scripts

        Returns:
            Generated script output
        """
        topic_text, topic_image = self.stage_session.get_topic()

        image_desc = None
        if topic_image:
            image_desc = await self._get_image_description(topic_image)

        if topic_text:
            user_message = OpenAIMessage(
                role="user",
                content=topic_text,
            )
        else:
            user_message = OpenAIMessage(
                role="user",
                content=image_desc,
            )

        system_message = OpenAIMessage(
            role="system",
            content=SCRIPT_SYSTEM_PROMPT_TEMPLATE,
        )

        llm_messages = [system_message, user_message]

        cumulated_chunks = []
        content_index = None
        output_message = Message()
        init_event = True
        model_name = self.config.get("model")

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

        script_text = output_message.content[0].text
        product_name, product_desc, slogan = parse_script(script_text)

        # Build data dict with script and parsed info
        data = {"script": script_text}
        for key, value in [
            ("product_name", product_name),
            ("product_desc", product_desc),
            ("slogan", slogan),
        ]:
            if value:
                data[key] = value

        # Generate image if we have product description and no topic image
        if not topic_image and product_desc:
            t2i_model = self.config.get("t2i_model")
            image_url = await generate_image_t2i(t2i_model, product_desc)
            data["image_url"] = image_url

        session_message = Message()
        session_message.add_content(DataContent(data=data))

        # Set stage messages
        self.stage_session.set_stage_message(
            Stage.SCRIPT,
            session_message,
        )

    async def _get_image_description(self, image_url: str) -> str:
        user_message = OpenAIMessage(
            role="user",
            content=[
                {
                    "type": "image_url",
                    "image_url": {
                        "url": image_url,
                        "detail": "low",
                    },
                },
                {
                    "type": "text",
                    "text": VL_USER_PROMPT,
                },
            ],
        )

        llm = BaseLLM()

        # 由于QVQ模型不支持非流式调用，我们通过流式调用收集完整响应
        full_desc = ""

        async for chunk in llm.astream(
            model=self.config.get("vl_model"),
            messages=[user_message],
        ):
            if chunk.choices and chunk.choices[0].delta.content:
                full_desc += chunk.choices[0].delta.content

        logger.info("get image description: %s" % full_desc)

        return full_desc


if __name__ == "__main__":
    import asyncio
    from demos.multimodal_generation.backend.test.utils import (
        test_handler,
        mock_stage_session,
    )

    stage_session = mock_stage_session(stage=Stage.SCRIPT)

    topic_text, topic_image = stage_session.get_topic()

    message = Message(
        role=Role.USER,
        content=[
            TextContent(text=topic_text),
            ImageContent(image_url=topic_image),
        ],
    )

    asyncio.run(test_handler(ScriptHandler, message, stage_session))
