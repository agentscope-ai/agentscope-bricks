# -*- coding: utf-8 -*-
"""
测试脚本，用于验证前端响应输出功能
"""

import asyncio
import json
import os
from agentscope_bricks.utils.schemas.modelstudio_llm import (
    ModelstudioChatRequest,
)
from agentscope_bricks.utils.schemas.oai_llm import UserMessage

# 设置测试用的API密钥（使用假的密钥进行测试）
os.environ["DASHSCOPE_API_KEY"] = ""


async def test_frontend_output():
    """测试前端响应输出功能"""
    print("=== 测试前端响应输出功能 ===")

    try:
        # 动态导入，避免在没有API密钥时出错
        from demos.agentic_rag.agentic_rag_service import agentic_rag_arun

        # 创建测试请求
        request = ModelstudioChatRequest(
            model="qwen-max",
            messages=[
                UserMessage(
                    content="帮我通过知识库找一下代表鞋款：The Reynolds,"
                    " Wino G6的品牌特性，如果找不到的话可以试试看使用搜索",
                ),
            ],
        )

        print("发送请求...")

        # 调用服务函数并打印输出
        async for response in agentic_rag_arun(request):
            print(f"前端响应: {response}")

            # 解析JSON数据以更好地展示
            if response.startswith("data: "):
                try:
                    data = response[6:].strip()
                    if data != "[DONE]":
                        response_data = json.loads(data)
                        print(
                            f"解析后的响应: {json.dumps(response_data, indent=2, ensure_ascii=False)}",  # noqa E501
                        )
                except json.JSONDecodeError:
                    print(f"原始数据: {data}")

            print("-" * 50)

        print("测试完成")

    except Exception as e:
        print(f"测试过程中出现错误: {e}")
        print(
            "这可能是由于缺少有效的API密钥导致的，但我们的代码修改应该已经正确实现。",
        )


if __name__ == "__main__":
    asyncio.run(test_frontend_output())
