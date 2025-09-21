# -*- coding: utf-8 -*-
# mypy: disable-error-code="valid-type"

from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, MessagesState, StateGraph
from pydantic import BaseModel, Field
from typing import Literal, Any, Union
import os
from agentscope_bricks.components import Component
from agentscope_bricks.adapters.langgraph.tool import LanggraphNodeAdapter
import asyncio


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

    async def _arun(self, args: SearchInput, **kwargs: Any) -> SearchOutput:
        """
        Run.
        """
        if "sf" in args.query.lower() or "san francisco" in args.query.lower():
            result = "It's 60 degrees and foggy."
        else:
            result = "It's 90 degrees and sunny."

        return SearchOutput(results=result)


tool_node = LanggraphNodeAdapter(
    [
        SearchComponent(
            name="Search_Component",
            description="Web search for weather or news",
            config={},
        ),
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
def call_model(state: MessagesState) -> dict:
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

# Initialize memory to persist state between graph runs
checkpointer = MemorySaver()

# Finally, we compile it!
# This compiles it into a LangChain Runnable,
# meaning you can use it as you would any other runnable.
# Note that we're (optionally) passing the memory when compiling the graph
app = workflow.compile(checkpointer=checkpointer)

# Use the Runnable
final_state = app.invoke(
    {"messages": [HumanMessage(content="what is the weather in sf")]},
    config={"configurable": {"thread_id": 42}},
)
print(final_state["messages"][-1].content)


async def arun() -> None:
    final_state_async = await app.ainvoke(
        {
            "messages": [
                {"role": "user", "content": "what is the weather in beijing"},
            ],
        },
        config={"configurable": {"thread_id": 42}},
    )
    print(final_state_async["messages"][-1].content)


asyncio.run(arun())
