# -*- coding: utf-8 -*-
import asyncio
import os

from agentscope_bricks.components.RAGs.modelstudio_rag import (
    ModelstudioRag,
    RagInput,
)
from agentscope_bricks.models.llm import BaseLLM

# 初始化RAG组件
rag_component = ModelstudioRag()
llm = BaseLLM()

# 用户消息示例
messages = [
    {
        "role": "system",
        "content": """
你是一位经验丰富的手机导购，任务是帮助客户对比手机参数，分析客户需求，推荐个性化建议。
# 知识库
请记住以下材料，他们可能对回答问题有帮助。
${documents}
""",
    },
    {"role": "user", "content": "有什么可以推荐的2000左右手机？"},
]

# 在modelstudio上面获取workspace_id和pipeline_id，参考文档 https://help.aliyun.com/zh/model-studio/user-guide/rag-knowledge-base#1927631810ebo   # noqa E501
pipeline_ids = ["0tgx5dbmv1"]

# 构造RAG输入
rag_input = RagInput(
    messages=messages,
    rag_options={"pipeline_ids": pipeline_ids},
    rest_token=1000,
)


# 调用RAG组件
async def main() -> None:
    try:
        # 异步运行RAG组件
        rag_output = await rag_component.arun(rag_input)

        # 输出结果
        print("RAG Result:", rag_output.rag_result)
        print("Updated Messages:")
        async for chunk in llm.astream(
            model="qwen-max",
            messages=rag_output.messages,
        ):
            print("LLM Result:", chunk)
    except Exception as e:
        print("Error during RAG execution:", e)


if __name__ == "__main__":
    # 请确保已设置环境变量 DASHSCOPE_API_KEY
    asyncio.run(main())
