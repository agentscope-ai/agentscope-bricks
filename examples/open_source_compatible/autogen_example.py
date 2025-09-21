# -*- coding: utf-8 -*-
# pylint:disable=no-untyped-def

import asyncio
import os

from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.messages import TextMessage
from autogen_core import CancellationToken
from autogen_ext.models.openai import OpenAIChatCompletionClient
from dotenv import load_dotenv

from agentscope_bricks.adapters.autogen.tool import AutogenToolAdapter
from agentscope_bricks.components.searches.modelstudio_search_lite import (
    ModelstudioSearchLite,
)

load_dotenv()


async def main() -> None:
    # Create the searches component
    search_component = ModelstudioSearchLite()

    # Create the autogen tool adapter
    search_tool = AutogenToolAdapter(search_component)

    # Create an agents with the searches tool
    model = OpenAIChatCompletionClient(
        model="qwen-plus",
        base_url=os.getenv("DASHSCOPE_BASE_URL"),
        api_key=os.getenv("DASHSCOPE_API_KEY"),  # pragma: allowlist secret
        model_info={
            "structured_output": False,
            "vision": False,
            "function_calling": True,
            "json_output": False,
            "family": "unknown",
        },
    )
    agent = AssistantAgent(
        "assistant",
        tools=[search_tool],
        model_client=model,
        reflect_on_tool_use=True,
    )

    # Use the agents
    response = await agent.on_messages(
        [TextMessage(content="北京天气如何？", source="user")],
        CancellationToken(),
    )
    print(response.chat_message)


asyncio.run(main())
