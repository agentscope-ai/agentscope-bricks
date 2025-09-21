# -*- coding: utf-8 -*-
# pylint:disable=no-untyped-def

import asyncio
import json
import os

from dotenv import load_dotenv

from agentscope_bricks.components.searches.modelstudio_search_lite import (
    ModelstudioSearchLite,
    SearchLiteInput,
    SearchLiteOutput,
)

load_dotenv()


try:
    # `pip install llama-index-llms-openai-like` if you don't already have it
    from llama_index.llms.openai_like import OpenAILike
    from llama_index.core.workflow import (
        Event,
        StartEvent,
        StopEvent,
        Workflow,
        step,
    )
except ImportError:
    raise ImportError(
        "Please install llama-index, " "llama-index-llms-openai-like",
    )


class SearchEvent(Event):
    search_result: str


class SearchFlow(Workflow):
    api_base = os.getenv(
        "DASHSCOPE_BASE_URL",
        "https://dashscope.aliyuncs.com/compatible-mode/v1",
    )
    llm = OpenAILike(
        api_key=os.getenv("DASHSCOPE_API_KEY"),
        api_base=api_base,
        model="qwen-plus",
        is_chat_model=True,
    )

    @step
    async def search_weather(self, ev: StartEvent) -> SearchEvent:
        query = ev.topic
        input = SearchLiteInput(query=query, count=5)
        result: SearchLiteOutput = await ModelstudioSearchLite().arun(input)
        search_result_str = ""
        for result in result.pages:
            search_result_str += json.dumps(result, ensure_ascii=False)
            search_result_str += "\n"
        return SearchEvent(
            search_result=f"user query: {query}, search "
            f"result: {search_result_str}",
        )

    @step
    async def generate_response(self, ev: SearchEvent) -> StopEvent:
        search_result = ev.search_result
        response = await self.llm.acomplete(search_result)
        return StopEvent(result=str(response))


async def main() -> None:
    w = SearchFlow(timeout=60, verbose=False)
    result = await w.run(topic="What's the weather in Beijing?")
    print(str(result))


if __name__ == "__main__":
    asyncio.run(main())
