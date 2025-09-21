# -*- coding: utf-8 -*-
# pylint:disable=no-untyped-def

import asyncio
import os
from typing import Any

from agentscope.agent import ReActAgent
from agentscope.formatter import DashScopeChatFormatter
from agentscope.memory import InMemoryMemory
from agentscope.message import Msg
from agentscope.model import DashScopeChatModel
from agentscope.tool import Toolkit
from pydantic import BaseModel, Field

from agentscope_bricks.adapters.agentscope.tool import (
    agentscope_tool_adapter,
)
from agentscope_bricks.components import Component


class SearchInput(BaseModel):
    """
    Search Input.
    """

    query: str = Field(..., title="Query")


class SearchOutput(BaseModel):
    """
    Search Output.
    """

    results: str


class SearchComponent(Component[SearchInput, SearchOutput]):
    """
    Search Component.
    """

    name = "Search"
    description = "web search for news and weather"

    async def _arun(self, args: SearchInput, **kwargs: Any) -> SearchOutput:
        """
        Run.
        """
        if "sf" in args.query.lower() or "san francisco" in args.query.lower():
            result = "It's 60 degrees and foggy."
        else:
            result = "It's 90 degrees and sunny."

        return SearchOutput(results=result)


async def main(content: str) -> None:
    toolkit = Toolkit()
    search_component = SearchComponent()
    toolkit.tools[search_component.name] = agentscope_tool_adapter(
        search_component,
    )

    agent = ReActAgent(
        name="Friday",
        sys_prompt="You're a helpful assistant named Friday.",
        model=DashScopeChatModel(
            model_name="qwen-turbo",
            api_key=os.environ["DASHSCOPE_API_KEY"],
            stream=True,
        ),
        memory=InMemoryMemory(),
        formatter=DashScopeChatFormatter(),
        toolkit=toolkit,
    )

    msg = Msg(
        name="user",
        role="user",
        content=content,
    )
    msg = await agent(msg)
    print(msg)


asyncio.run(main("杭州天气如何？"))
