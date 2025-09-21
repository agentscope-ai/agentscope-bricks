# -*- coding: utf-8 -*-
import asyncio

from agentscope_runtime.engine import Runner
from agentscope_runtime.engine.schemas.agent_schemas import (
    AgentRequest,
    MessageType,
    RunStatus,
)
from agentscope_runtime.engine.services.context_manager import (
    create_context_manager,
)


async def simple_call_agent(query, runner, user_id=None, session_id=None):
    request = AgentRequest(
        model="qwen-plus",
        input=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": query,
                    },
                ],
            },
        ],
        session_id=session_id,
    )
    all_result = ""
    async for message in runner.stream_query(
        user_id=user_id,
        request=request,
    ):
        if (
            message.object == "message"
            and MessageType.MESSAGE == message.type
            and RunStatus.Completed == message.status
        ):
            all_result = message.content[0].text
        print("agent output", message)
    print("📝 Agent final output:", all_result)
    return all_result


async def simple_call_agent_direct(agent, query):
    async with create_context_manager() as context_manager:
        runner = Runner(
            agent=agent,
            context_manager=context_manager,
        )
        result = await simple_call_agent(
            query,
            runner,
        )
    return result


if __name__ == "__main__":

    agent_type = input(
        "\nchoice the agent type:\n"
        "1. agentscope\n"
        "2. langgraph\n"
        "3. simple agent\n"
        "Choice agent from (1-3): ",
    ).strip()

    try:
        if agent_type == "1":
            from react_agent_with_agentscope import agentscope_agent as agent
        elif agent_type == "2":
            from react_agent_with_langgraph import langgraph_agent as agent
        elif agent_type == "3":
            from react_agent_with_customize_agent import simple_agent as agent
        else:
            print("❌ Invalid choice")
            exit(1)
        asyncio.run(simple_call_agent_direct(agent, input("Input query: ")))
    except Exception as e:
        print(f"❌ error: {e}")
        import traceback

        traceback.print_exc()
