# -*- coding: utf-8 -*-
import asyncio
from contextlib import asynccontextmanager

from agentscope_runtime.engine.deployers import LocalDeployManager
from agentscope_runtime.engine.runner import Runner
from agentscope_runtime.engine.services.context_manager import ContextManager
from agentscope_runtime.engine.services.session_history_service import (
    InMemorySessionHistoryService,
)
from agentscope_runtime.engine.services.environment_manager import (
    create_environment_manager,
)
from agentscope_runtime.engine.deployers.adapter.responses.response_api_protocol_adapter import (  # noqa E501
    ResponseAPIDefaultAdapter,
)

responses_adapter = ResponseAPIDefaultAdapter()

USER_ID = "user_1"
SESSION_ID = "session_001"  # Using a fixed ID for simplicity


"""
curl http://localhost:8090/process \
-X POST -H "Content-Type: application/json" \
-d '{
        "model": "qwen-max",
        "input": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "杭州在哪里？"
                    }
                ]
            }
        ]
    }'
"""


async def prepare_context():
    session_history_service = InMemorySessionHistoryService()
    await session_history_service.create_session(
        user_id=USER_ID,
        session_id=SESSION_ID,
    )
    context_manager = ContextManager(
        session_history_service=session_history_service,
    )

    return context_manager


@asynccontextmanager
async def create_runner(agent):

    context_manager = await prepare_context()
    async with context_manager:
        async with create_environment_manager() as env_manager:
            runner = Runner(
                agent=agent,
                context_manager=context_manager,
                environment_manager=env_manager,
            )
            yield runner


async def deploy_agent(runner):
    # 创建部署管理器
    deploy_manager = LocalDeployManager(
        host="localhost",
        port=8090,
    )

    # 将智能体部署为流式服务
    deploy_result = await runner.deploy(
        deploy_manager=deploy_manager,
        endpoint_path="/process",
        stream=True,  # Enable streaming responses
        protocol_adapters=[responses_adapter],
    )
    print(f"🚀Agent deploy to: {deploy_result}")
    print(f"🌐url: {deploy_manager.service_url}")
    print(f"💚health endpoint: {deploy_manager.service_url}/health")

    return deploy_manager


async def run_deployment(agent):
    async with create_runner(agent) as runner:
        deploy_manager = await deploy_agent(runner)

    # Keep the service running (in production, you'd handle this differently)
    print("🏃 Service is running...")

    return deploy_manager


async def main(agent):
    try:
        deploy_manager = await run_deployment(agent)

        # Keep the main script alive. The server is running in a daemon thread.
        while True:
            await asyncio.sleep(1)

    except (KeyboardInterrupt, asyncio.CancelledError):
        # This block will be executed when you press Ctrl+C.
        print("\nShutdown signal received. Stopping the service...")
        if deploy_manager.is_running:
            await deploy_manager.stop()
        print("✅ Service stopped.")
    except Exception as e:
        print(f"An error occurred: {e}")
        if deploy_manager.is_running:
            await deploy_manager.stop()


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
        asyncio.run(main(agent))
    except Exception as e:
        print(f"❌ error: {e}")
        import traceback

        traceback.print_exc()
