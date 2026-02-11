# -*- coding: utf-8 -*-
import requests
import asyncio
import os
from typing import (
    Dict,
    Sequence,
    Any,
    Generic,
    TypeVar,
    Union,
)
from pydantic import BaseModel
import json
from typing_extensions import Literal, TypeAlias
from agents.agent import (
    AgentRequest,
)
from agentscope_bricks.utils.logger_util import logger

AGENT_URL = os.getenv(
    "AGENT_API_URL",
    "https://dashscope.aliyuncs.com/api/v2/apps/gui-owl/gui_agent_server",
)


class GuiAgentResponse(BaseModel):
    request_id: str
    session_id: str
    thought: str
    explanation: str
    action: str
    action_params: str
    operation: str


GuiAgentMessageT = TypeVar(
    "GuiAgentMessageT",
    bound=AgentRequest,
    contravariant=True,
)

GuiAgents: TypeAlias = Literal["phone_use"]
GuiAgentReturnT = TypeVar(
    "GuiAgentReturnT",
    bound=Union[GuiAgentResponse],
    covariant=True,
)


class GuiAgent(Generic[GuiAgentMessageT, GuiAgentReturnT]):

    def model_dump_json(self) -> str:
        """Serialize the model information to JSON string.

        Returns:
            str: JSON string containing model type and client information.
        """
        info = {"client": str(self.client)}
        return json.dumps(info)

    async def run(
        self,
        messages: Sequence[Union[GuiAgentMessageT, Dict]],
        mode: Union[str, GuiAgents] = "phone_use",
    ) -> dict | None:
        try:
            headers = {
                "Content-Type": "application/json",
                "Authorization": "Bearer "
                + f'{os.getenv("DASHSCOPE_API_KEY", None)}',
            }

            data = {
                "app_id": "gui-owl",
                "input": messages,
            }

            logger.info(f"发送请求messages: {data}")
            # 添加重试逻辑
            max_retries = 3
            retry_delay = 1  # 初始重试延迟（秒）

            for attempt in range(max_retries):
                # 使用异步方式发送请求
                def make_request():
                    return requests.post(
                        AGENT_URL,
                        headers=headers,
                        data=json.dumps(data),
                        timeout=200,
                    )

                response = await asyncio.to_thread(make_request)
                if response.status_code == 200:
                    # 请求成功，跳出重试循环
                    break
                else:
                    logger.error(
                        f"GUI服务请求失败: {response.status_code}, {response.text}",
                    )
                    if attempt < max_retries - 1:  # 如果不是最后一次尝试
                        logger.info(
                            f"第 {attempt + 2} 次请求失败，{retry_delay} "
                            "秒后进行第 {attempt + 3} 次重试...",
                        )
                        await asyncio.sleep(retry_delay)
                        retry_delay *= 2  # 指数退避
                    else:
                        logger.error(
                            "所有重试尝试都失败，请检查网络连接或稍后再试。",
                        )
                        # 最后一次尝试也失败了，抛出异常
                        raise Exception(
                            f"GUI服务请求失败 {response.status_code},"
                            f" {response.text}",
                        )

            result = response.json()
            logger.info(f"Gui API Response: {result}")

            # 提取基础信息
            # api_output = result.get("output", {})
            request_id = result.get("id", "")
            session_id = result.get("session_id", "")
            # 尝试从不同位置提取response数据
            operation_all = {}
            api_output = result.get("output", [])
            if isinstance(api_output, list) and len(api_output) > 0:
                content = api_output[0].get("content", [])
                if (
                    isinstance(content, list)
                    and len(content) > 0
                    and isinstance(content[0], dict)
                ):
                    operation_all = content[0].get("data", {})

            # 提取字段，适配两种模式
            thought = operation_all.get("Thought", "")
            if not thought:
                thought = operation_all.get("thought", "")  # 小写版本

            operation = ""
            action_params = {}
            action = ""
            if mode == "pc_use":
                action = operation_all.get("action_type", "")
                action_params = operation_all.get(
                    "action_parameter",
                    {},
                )  # 注意这里可能是action_parameter而不是action_params
                explanation = operation_all.get("explanation", "")
            else:
                # 手机模式
                operation = operation_all.get("Operation", "")
                if not operation:
                    operation = operation_all.get("operation", "")  # 小写版本
                explanation = operation_all.get("Explanation", "")
                if not explanation:
                    explanation = operation_all.get(
                        "explanation",
                        "",
                    )  # 小写版本

            mobile_use_response = {
                "request_id": request_id,
                "session_id": session_id,
                "thought": thought,
                "explanation": explanation,
                "action": action,
                "action_params": action_params,
                "operation": operation,
            }
            logger.info(f"mobile_use_response: {mobile_use_response}")
            return mobile_use_response
        except Exception as e:
            print(f"Error when calling {mode}: {e}")
            raise e

    async def arun(
        self,
        messages: Sequence[Union[GuiAgentMessageT, Dict]],
        model: Union[str, GuiAgents],
    ) -> GuiAgentResponse | None:
        mobile_use_response = await self.run(messages, model)
        response = GuiAgentResponse(
            request_id=mobile_use_response.get("request_id", ""),
            session_id=mobile_use_response.get("session_id", ""),
            explanation=mobile_use_response.get("explanation", ""),
            action_params=mobile_use_response.get("action_params", ""),
            action=mobile_use_response.get("action", ""),
            operation=mobile_use_response.get("operation", ""),
            thought=mobile_use_response.get("thought", ""),
        )
        return response


def main() -> None:
    use_model = GuiAgent()
    message = [
        {
            "role": "user",
            "content": [
                {
                    "type": "data",
                    "data": {
                        "messages": [
                            {
                                "image": "",
                            },
                            {
                                "instruction": "打开微博",
                            },
                            {
                                "session_id": "",
                            },
                            {
                                "thought_language": "chinese",
                            },
                            {
                                "device_type": "mobile",
                            },
                            {
                                "model_name": "qwen2.5-vl-72b-instruct-agent",
                            },
                            {
                                "pipeline_type": "agent",
                            },
                            {
                                "use_add_info_generate": "false",
                            },
                            {
                                "param_list": [
                                    {
                                        "add_info": "",
                                    },
                                ],
                            },
                        ],
                    },
                },
            ],
        },
    ]
    # 调用同步方法异步任务run

    output = asyncio.run(use_model.run(message, "phone_use"))
    print(output)


if __name__ == "__main__":
    main()
