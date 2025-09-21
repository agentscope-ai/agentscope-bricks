# -*- coding: utf-8 -*-
import os
import json
from typing import Literal

from agentscope_runtime.engine.agents.langgraph_agent import LangGraphAgent
from langchain_openai import ChatOpenAI
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.graph import END, START, MessagesState, StateGraph


from agentscope_bricks.adapters.langgraph.tool import LanggraphNodeAdapter
from agentscope_bricks.components.searches.modelstudio_search_lite import (
    ModelstudioSearchLite,
)

tool_node = LanggraphNodeAdapter(
    [
        ModelstudioSearchLite(),
    ],
)

api_key = os.getenv("DASHSCOPE_API_KEY")

model = ChatOpenAI(
    model="qwen-turbo",
    openai_api_key=api_key,
    openai_api_base="https://dashscope.aliyuncs.com/compatible-mode/v1",
).bind_tools(tool_node.tool_schemas)


# Define the function that determines whether to continue or not
def should_continue(state: MessagesState) -> Literal["tools", END]:
    messages = state["messages"]
    last_message = messages[-1]
    # If the LLM makes a tool call, then we route to the "tools" node
    if last_message.tool_calls:
        return "tools"
    # Otherwise, we stop (reply to the user)
    return END


# Define the function that calls the model
def call_model(state: MessagesState):
    messages = state["messages"]
    response = model.invoke(messages)
    # We return a list, because this will get added to the existing list
    return {"messages": [response]}


# Define a new graph
workflow = StateGraph(MessagesState)

# Define the two nodes we will cycle between
workflow.add_node("agents", call_model)
workflow.add_node("tools", tool_node)

# Set the entrypoint as `agents`
# This means that this node is the first one called
workflow.add_edge(START, "agents")

# We now add a conditional edge
workflow.add_conditional_edges(
    # First, we define the start node. We use `agents`.
    # This means these are the edges taken after the `agents` node is called.
    "agents",
    # Next, we pass in the function that will determine which
    # node is called next.
    should_continue,
)

# We now add a normal edge from `tools` to `agents`.
# This means that after `tools` is called, `agents` node is called next.
workflow.add_edge("tools", "agents")

# Finally, we compile it!
# This compiles it into a LangChain Runnable,
# meaning you can use it as you would any other runnable.
# Note that we're (optionally) passing the memory when compiling the graph
compiled_graph = workflow.compile(
    name="pro-search-agent",
)


def human_ai_message_to_dict(obj):

    if isinstance(obj, AIMessage):
        return {
            "role": "assistant",
            "content": obj.content,
        }
    if isinstance(obj, ToolMessage):
        return {
            "role": "tool",
            "content": obj.content,
        }
    return None


def state_folder(messages):
    if len(messages) > 0:
        return {"messages": [messages[0]]}
    else:
        return []


def state_unfolder(state):
    state_jsons = json.dumps(
        state,
        default=human_ai_message_to_dict,
        ensure_ascii=False,
    )
    return state_jsons


langgraph_agent = LangGraphAgent(
    compiled_graph,
    state_folder=state_folder,
    state_unfolder=state_unfolder,
)
