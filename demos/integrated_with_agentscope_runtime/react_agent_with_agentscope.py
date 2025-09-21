# -*- coding: utf-8 -*-
import os

from agentscope.agent import ReActAgent
from agentscope.model import DashScopeChatModel
from agentscope_runtime.engine.agents.agentscope_agent import AgentScopeAgent

from agentscope_bricks.adapters.agentscope_runtime.tool import (
    AgentScopeRuntimeToolAdapter,
)
from agentscope_bricks.components.searches.modelstudio_search_lite import (
    ModelstudioSearchLite,
)

# Initialize the language model
model = DashScopeChatModel(
    "qwen-max",
    api_key=os.getenv("DASHSCOPE_API_KEY"),
)

SYSTEM_PROMPT = """You are a Web-Using AI assistant.

# Objective
Your goal is to complete given tasks by using registry tools
"""

print("✅系统提示词已配置")

# apply Search Tool
search_tool = AgentScopeRuntimeToolAdapter(ModelstudioSearchLite())

# Create the AgentScope agent
agentscope_agent = AgentScopeAgent(
    name="Friday",
    model=model,
    agent_config={
        "sys_prompt": SYSTEM_PROMPT,
    },
    tools=[search_tool],
    agent_builder=ReActAgent,
)
