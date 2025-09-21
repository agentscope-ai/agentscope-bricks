# -*- coding: utf-8 -*-
"""
Test script for agentic RAG service
"""

import asyncio
import json
import aiohttp


async def test_rag_query():
    """Test RAG query"""
    url = "http://127.0.0.1:8092/api/v1/chat/completions"

    payload = {
        "model": "qwen-max",
        "messages": [
            {
                "role": "user",
                "content": "请帮我分析一下，PRIMEKNIT编织鞋面的特点，他对于整个鞋服市场"
                "的影响大吗，占比在多少？可以通过web搜索或者rag知识库等方式"
                "找到资料，并深入分析一下",
            },
        ],
        "rag_options": {
            "pipeline_ids": ["pipvjc32u3", "e7l89mtxfq"],
            "maximum_allowed_chunk_num": 10,
        },
    }

    headers = {
        "Content-Type": "application/json",
    }

    print("=== 测试RAG查询（混合策略） ===")
    async with aiohttp.ClientSession() as session:
        async with session.post(
            url,
            json=payload,
            headers=headers,
        ) as response:
            print(f"Status: {response.status}")
            print("Response:")
            async for line in response.content:
                if line.startswith(b"data: "):
                    data = line[6:].decode("utf-8").strip()
                    if data != "[DONE]":
                        try:
                            response_data = json.loads(data)
                            print("--- 四模块结构化输出 ---")
                            if (
                                "thinking" in response_data
                                and response_data["thinking"]
                            ):
                                print("【思考模块】:")
                                thinking_process = response_data["thinking"][
                                    "process"
                                ]
                                print(thinking_process)
                                print()

                            if (
                                "task_list" in response_data
                                and response_data["task_list"]
                            ):
                                print("【任务列表模块】:")
                                task_list = response_data["task_list"]
                                print(f"总任务数: {task_list['total_tasks']}")
                                print(
                                    f"当前执行任务ID: {task_list['current_task_id']}",  # noqa E501
                                )
                                print("任务详情:")
                                for task in task_list["tasks"]:
                                    status_icon = (
                                        "⏳"
                                        if task["status"] == "in_progress"
                                        else (
                                            "✅"
                                            if task["status"] == "completed"
                                            else (
                                                "⏭️"
                                                if task["status"] == "skipped"
                                                else "⏸️"
                                            )
                                        )
                                    )
                                    reason = (
                                        f" ({task['reason']})"
                                        if task.get("reason")
                                        else ""
                                    )
                                    print(
                                        f"  {status_icon} {task['id']}. {task['description']} [{task['status']}]{reason}",  # noqa E501
                                    )
                                print()

                            if "rag" in response_data and response_data["rag"]:
                                print("【RAG模块】:")
                                print(f"查询: {response_data['rag']['query']}")
                                print(
                                    f"状态: {'成功' if response_data['rag']['status'] == 0 else '失败'}",  # noqa E501
                                )
                                print("召回文档:")
                                for i, chunk in enumerate(
                                    response_data["rag"]["chunks"],
                                ):
                                    print(
                                        f"  [{i+1}] {chunk['content'][:100]}...",  # noqa E501
                                    )
                                print()

                            if (
                                "search" in response_data
                                and response_data["search"]
                            ):
                                print("【搜索模块】:")
                                print(
                                    f"查询: {response_data['search']['query']}",
                                )
                                print(
                                    f"状态: {'成功' if response_data['search']['status'] == 0 else '失败'}",  # noqa E501
                                )
                                print("搜索结果:")
                                for i, result in enumerate(
                                    response_data["search"]["results"],
                                ):
                                    print(f"  [{i + 1}] {result['title']}")
                                    print(
                                        f"      {result['snippet'][:100]}...",
                                    )
                                print()

                            if "final_response" in response_data:
                                print("【最终回答】:")
                                print(response_data["final_response"])
                                print()
                        except json.JSONDecodeError:
                            print(f"Raw data: {data}")


async def test_search_query():
    """Test search query"""
    url = "http://127.0.0.1:8092/api/v1/chat/completions"

    payload = {
        "model": "qwen-max",
        "messages": [
            {"role": "user", "content": "今天天气怎么样？"},
        ],
    }

    headers = {
        "Content-Type": "application/json",
    }

    print("\n=== 测试搜索查询 ===")
    async with aiohttp.ClientSession() as session:
        async with session.post(
            url,
            json=payload,
            headers=headers,
        ) as response:
            print(f"Status: {response.status}")
            print("Response:")
            async for line in response.content:
                if line.startswith(b"data: "):
                    data = line[6:].decode("utf-8").strip()
                    if data != "[DONE]":
                        try:
                            response_data = json.loads(data)
                            print("--- 四模块结构化输出 ---")
                            if (
                                "thinking" in response_data
                                and response_data["thinking"]
                            ):
                                print("【思考模块】:")
                                thinking_process = response_data["thinking"][
                                    "process"
                                ]
                                print(thinking_process)
                                print()

                            if (
                                "task_list" in response_data
                                and response_data["task_list"]
                            ):
                                print("【任务列表模块】:")
                                task_list = response_data["task_list"]
                                print(f"总任务数: {task_list['total_tasks']}")
                                print(
                                    f"当前执行任务ID: {task_list['current_task_id']}",  # noqa E501
                                )
                                print("任务详情:")
                                for task in task_list["tasks"]:
                                    status_icon = (
                                        "⏳"
                                        if task["status"] == "in_progress"
                                        else (
                                            "✅"
                                            if task["status"] == "completed"
                                            else (
                                                "⏭️"
                                                if task["status"] == "skipped"
                                                else "⏸️"
                                            )
                                        )
                                    )
                                    reason = (
                                        f" ({task['reason']})"
                                        if task.get("reason")
                                        else ""
                                    )
                                    print(
                                        f"  {status_icon} {task['id']}. {task['description']} [{task['status']}]{reason}",  # noqa E501
                                    )
                                print()

                            if (
                                "search" in response_data
                                and response_data["search"]
                            ):
                                print("【搜索模块】:")
                                print(
                                    f"查询: {response_data['search']['query']}",
                                )
                                print(
                                    f"状态: {'成功' if response_data['search']['status'] == 0 else '失败'}",  # noqa E501
                                )
                                print("搜索结果:")
                                for i, result in enumerate(
                                    response_data["search"]["results"],
                                ):
                                    print(f"  [{i + 1}] {result['title']}")
                                    print(
                                        f"      {result['snippet'][:100]}...",
                                    )
                                print()

                            if "rag" in response_data and response_data["rag"]:
                                print("【RAG模块】:")
                                print(f"查询: {response_data['rag']['query']}")
                                print(
                                    f"状态: {'成功' if response_data['rag']['status'] == 0 else '失败'}",  # noqa E501
                                )
                                print("召回文档:")
                                for i, chunk in enumerate(
                                    response_data["rag"]["chunks"],
                                ):
                                    print(
                                        f"  [{i+1}] {chunk['content'][:100]}...",  # noqa E501
                                    )
                                print()

                            if "final_response" in response_data:
                                print("【最终回答】:")
                                print(response_data["final_response"])
                                print()
                        except json.JSONDecodeError:
                            print(f"Raw data: {data}")


async def main():
    """Main test function"""
    print("测试 Agentic RAG Service 的四模块输出...")

    # Test RAG query
    await test_rag_query()

    # Test search query
    await test_search_query()


if __name__ == "__main__":
    asyncio.run(main())
