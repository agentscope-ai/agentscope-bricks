# -*- coding: utf-8 -*-
# pylint:disable=no-untyped-def

import asyncio
import json
from typing import Dict, List, Union, Any

from agentscope_bricks.base.prompt import PromptTemplate
from agentscope_bricks.utils.schemas.oai_llm import OpenAIMessage
from agentscope_bricks.components.searches.modelstudio_search_lite import (
    ModelstudioSearchLite,
    SearchLiteOutput,
    SearchLiteInput,
)
from agentscope_bricks.models.llm import BaseLLM
from agentscope_bricks.utils.schemas.oai_llm import Role

search_component = ModelstudioSearchLite()
llm = BaseLLM()

user_messages = [{"role": "user", "content": "南京的天气如何？"}]

MODELSTUDIO_KNOWLEDGE_TEMPLATE = """## 来自 {source} 的内容：

```
{content}
```"""
knowledge_prompt_builder = PromptTemplate.from_template(
    MODELSTUDIO_KNOWLEDGE_TEMPLATE,
    template_format="f-string",
)


# calling searches component
async def handle_search_context(
    messages: List[Union[OpenAIMessage, Dict]],
    **kwargs: Any,
) -> Union[None, SearchLiteOutput]:

    search_input = SearchLiteInput(
        query=messages[0]["content"],
    )

    # 调用百炼搜索组件
    result = await search_component.arun(search_input, **kwargs)
    return result


# build prompt
def get_updated_system_prompt(
    messages: List[Union[OpenAIMessage, Dict]],
    search_output: SearchLiteOutput,
) -> List[Union[OpenAIMessage, Dict]]:
    for i, message in enumerate(messages):
        if not isinstance(message, OpenAIMessage):
            messages[i] = OpenAIMessage(**message)
    knowledge_prompt = "# 知识库/n/n"
    knowledge_prompt += json.dumps(search_output.pages)
    if messages[0].role == Role.SYSTEM:
        messages[0].content = messages[0].content + knowledge_prompt
    else:
        messages.insert(
            0,
            OpenAIMessage(
                role=Role.SYSTEM,
                content=knowledge_prompt,
            ),
        )
    return messages


# 主函数
async def main() -> None:
    try:
        # 调用 handle_search_context 处理搜索上下文 , user id is required
        # for searches and match with your sk
        search_result = await handle_search_context(
            user_messages,
        )
        print(f"searches result: {search_result}")
        if search_result:
            # 构建更新后的系统提示
            updated_messages = get_updated_system_prompt(
                user_messages,
                search_result,
            )

            # 异步调用 LLM 并处理结果
            async for chunk in llm.astream(
                model="qwen-max",
                messages=updated_messages,
            ):
                print("LLM Result:", chunk)
    except Exception as e:
        print("Error during searches or LLM execution:", e)


if __name__ == "__main__":
    # please set up DASHSCOPE_API_KEY in your environment variables
    asyncio.run(main())
