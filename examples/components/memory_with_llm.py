# -*- coding: utf-8 -*-
# type: ignore

import asyncio
import os
import time
from typing import List

from agentscope_bricks.components.memory.modelstudio_memory import (
    AddMemory,
    SearchMemory,
    ListMemory,
    DeleteMemory,
    AddMemoryInput,
    SearchMemoryInput,
    ListMemoryInput,
    DeleteMemoryInput,
    AddMemoryOutput,
    SearchMemoryOutput,
    ListMemoryOutput,
    DeleteMemoryOutput,
    Message,
)
from agentscope_bricks.models.llm import BaseLLM
from agentscope_bricks.utils.schemas.oai_llm import Parameters

# ============= Configuration =============
DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY", "")
# Configure the end user's ID to ensure their memory is isolated from others.
END_USER_ID = os.getenv("END_USER_ID", "default")


# Check required environment variables
if not DASHSCOPE_API_KEY:
    raise ValueError("DASHSCOPE_API_KEY environment variable is not set")

# ============= Component Initialization =============
add_memory = AddMemory()
search_memory = SearchMemory()
list_memory = ListMemory()
delete_memory = DeleteMemory()
llm = BaseLLM()


# ============= Example Data =============
def get_example_messages() -> List[Message]:
    """Get example conversation messages for memory storage."""
    return [
        Message(role="user", content="每天上午11点提醒我点外卖。"),
        Message(role="assistant", content="没问题"),
        Message(
            role="user",
            content=[
                {
                    "type": "image_url",
                    "image_url": {
                        "url": "https://help-static-aliyun-doc.aliyuncs.com/file-manage-files/zh-CN/20241022/emyrja/dog_and_girl.jpeg",  # noqa E501
                    },
                    "description": "【标题】白板文字记录与会议纪要提醒\n【内容】白板内容涉及近代教育体系建立的相关知识点，包括维新派活动、清末新政、资产阶级革命派活动等。具体内容如下：\n- 维新派活动：（1）近代学制特点；（2）废科举、兴学堂的过程。\n- 清末新政：行政设立学部和提学使司。\n- 资产阶级革命派活动：爱国学社、中华革命党。\n- 近代学制特点：目的、系统性、内容、班级授课与学年制度、对待儿童方式、课程比重等。",  # noqa E501
                },
                {
                    "type": "text",
                    "text": "记录一下白板这些文字，明天10点提醒我整理会议纪要。",
                },
            ],
        ),
        Message(role="assistant", content="好的"),
    ]


# ============= Memory Operations =============
async def add_memory_example() -> AddMemoryOutput:
    """Add conversation messages to memory."""
    return await add_memory.arun(
        AddMemoryInput(
            user_id=END_USER_ID,
            messages=get_example_messages(),
            source="rayneo",
            timestamp=int(time.time()),
            meta_data={
                "location_name": "北京",
                "geo_coordinate": "116.481499,39.990475",
                "media_desc": [
                    {
                        "url": "https://help-static-aliyun-doc.aliyuncs.com/file-manage-files/zh-CN/20241022/emyrja/dog_and_girl.jpeg",  # noqa E501
                        "description": "【标题】白板文字记录与会议纪要提醒\n【内容】白板内容涉及近代教育体系建立的相关知识点，包括维新派活动、清末新政、资产阶级革命派活动等。具体内容如下：\n- 维新派活动：（1）近代学制特点；（2）废科举、兴学堂的过程。\n- 清末新政：行政设立学部和提学使司。\n- 资产阶级革命派活动：爱国学社、中华革命党。\n- 近代学制特点：目的、系统性、内容、班级授课与学年制度、对待儿童方式、课程比重等。",  # noqa E501
                    },
                ],
            },
        ),
    )


async def list_memory_example() -> ListMemoryOutput:
    """List all memory nodes for a user."""
    return await list_memory.arun(
        ListMemoryInput(
            user_id=END_USER_ID,
            page_num=1,
            page_size=10,
        ),
    )


async def search_memory_example(messages: List[Message]) -> SearchMemoryOutput:
    """Search for relevant memories based on query."""
    return await search_memory.arun(
        SearchMemoryInput(
            user_id=END_USER_ID,
            messages=messages,
            top_k=5,
            min_score=0,
        ),
    )


async def delete_memory_example(memory_node_id: str) -> DeleteMemoryOutput:
    """Delete a specific memory node."""
    return await delete_memory.arun(
        DeleteMemoryInput(
            user_id=END_USER_ID,
            memory_node_id=memory_node_id,
        ),
    )


# ============= LLM Integration =============
async def get_llm_response(
    search_result: SearchMemoryOutput,
    user_query: str,
) -> None:
    """Get LLM response based on retrieved memories."""
    system_prompt = f"""You are an experienced Assistant. Please answer the question based on the retrieved memories.

Retrieved memories:
{chr(10).join([f"- {node.content}" for node in search_result.memory_nodes])}
"""

    llm_messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_query},
    ]

    parameters = Parameters(
        stream=True,
        stream_options={"include_usage": True},
    )
    async for chunk in llm.astream(
        model="qwen-max",
        messages=llm_messages,
        parameters=parameters,
    ):
        print(chunk.choices[0].delta, end="\n", flush=True)


# ============= Main Execution =============
async def main() -> None:
    """Main execution function."""
    try:
        # 1. Add memory
        print("\n=== Adding Memory ===")
        add_result = await add_memory_example()
        print("Add Memory Result:", add_result)

        time.sleep(5)
        # 2. Delete the newly added memory node
        print("\n=== Deleting Memory ===")
        if add_result.memory_nodes:
            memory_node_id = add_result.memory_nodes[0].memory_node_id
            if memory_node_id:
                delete_result = await delete_memory_example(memory_node_id)
                print("Delete Memory Result:", delete_result)

        time.sleep(5)
        # 3. List memory
        print("\n=== Listing Memory ===")
        list_result = await list_memory_example()
        print("List Memory Result:")
        print(f"Request ID: {list_result.request_id}")
        for node in list_result.memory_nodes:
            print(f"Memory Node ID: {node.memory_node_id}")
            print(f"Memory Node Content: {node.content}")

        time.sleep(5)
        # 4. Search memory
        user_query = "明天需要提醒我什么事？"
        print("\n=== Searching Memory ===")
        search_result = await search_memory_example(
            [Message(role="user", content=user_query)],
        )
        print("Search Memory Result:", search_result)

        # 5. Get LLM response
        print("\n=== Getting LLM Response ===")
        await get_llm_response(search_result, user_query=user_query)

    except Exception as e:
        print("Error during execution:", e)


if __name__ == "__main__":
    asyncio.run(main())
