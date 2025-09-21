# -*- coding: utf-8 -*-
import asyncio
from contextlib import asynccontextmanager

from agentscope_runtime.engine.deployers import LocalDeployManager
from agentscope_runtime.engine.runner import Runner
from agentscope_runtime.engine.services.context_manager import ContextManager
from agentscope_runtime.engine.services.session_history_service import (
    InMemorySessionHistoryService,
)

# Sandbox service import moved to try-catch block to handle optional dependency
from pathlib import Path
from dotenv import load_dotenv
from agent import FilmAgent

"""
curl http://localhost:8090/process \
-X POST -H "Content-Type: application/json" \
-d '{
        "model": "qwen-max",
        "session_id": "session_id_1",
        "input": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "百炼橙汁"
                    }
                ]
            }
        ]
    }'
"""


async def prepare_context():
    session_history_service = InMemorySessionHistoryService()
    context_manager = ContextManager(
        session_history_service=session_history_service,
    )

    return context_manager


@asynccontextmanager
async def create_runner():

    # create agent
    agent = FilmAgent(
        name="Friday",
        agent_config={
            "sys_prompt": "You're a helpful assistant named {name}.",
        },
    )

    context_manager = await prepare_context()
    async with context_manager:
        # Create runner without environment manager
        runner = Runner(
            agent=agent,
            context_manager=context_manager,
            environment_manager=None,
        )
        print("✅ Runner创建成功 (without environment manager)")
        yield runner


async def deploy_agent(runner):
    # 创建部署管理器
    deploy_manager = LocalDeployManager(
        host="0.0.0.0",
        port=8080,
    )

    # 将智能体部署为流式服务
    deploy_result = await runner.deploy(
        deploy_manager=deploy_manager,
        endpoint_path="/process",
        stream=True,  # Enable streaming responses
    )
    print(f"🚀智能体部署在: {deploy_result}")
    print(f"🌐服务URL: {deploy_manager.service_url}")
    print(f"💚 健康检查: {deploy_manager.service_url}/health")

    return deploy_manager


async def run_deployment():
    async with create_runner() as runner:
        deploy_manager = await deploy_agent(runner)

    # Keep the service running (in production, you'd handle this differently)
    print("🏃 Service is running...")

    return deploy_manager


async def main():
    deploy_manager = None
    try:
        deploy_manager = await run_deployment()

        # Keep the main script alive. The server is running in a daemon thread.
        while True:
            await asyncio.sleep(1)

    except (KeyboardInterrupt, asyncio.CancelledError):
        # This block will be executed when you press Ctrl+C.
        print("\nShutdown signal received. Stopping the service...")
        if deploy_manager and deploy_manager.is_running:
            await deploy_manager.stop()
        print("✅ Service stopped.")
    except Exception as e:
        print(f"An error occurred: {e}")
        if deploy_manager and deploy_manager.is_running:
            await deploy_manager.stop()


if __name__ == "__main__":
    # Load .env file from current directory (where app.py is located)
    current_dir = Path(__file__).parent
    env_file = current_dir / ".env"
    load_dotenv(dotenv_path=env_file)
    asyncio.run(main())
