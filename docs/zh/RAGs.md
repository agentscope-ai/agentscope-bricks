# 检索增强生成组件 (RAGs)

本目录包含RAG（Retrieval-Augmented Generation）相关组件，提供知识库检索和增强生成功能。

## 📋 组件列表

### 1. ModelstudioRag - 百炼RAG组件
核心的检索增强生成服务，能够召回用户在百炼平台上的知识库信息并进行智能回答。

**前置使用条件：**
- 有效的DashScope API密钥
- 配置百炼HTTP基础URL
- 用户已在百炼平台创建知识库
- 知识库中有相关文档内容

**输入参数 (RagInput)：**
- `messages` (List): 对话消息列表
- `rag_options` (Dict): RAG选项配置
  - `knowledge_base_id`: 知识库ID
  - `top_k`: 检索条目数量
  - `score_threshold`: 相似度阈值
  - `enable_citation`: 是否启用引用
- `rest_token` (str): 认证令牌
- `image_urls` (List[str], 可选): 图片URL列表（多模态支持）
- `workspace_id` (str, 可选): 工作空间ID

**输出参数 (RagOutput)：**
- `raw_result` (str): 原始检索结果
- `rag_result` (Dict): 结构化RAG结果
  - `answer`: 生成的答案
  - `references`: 相关文档引用
  - `confidence`: 置信度分数
- `messages` (List): 处理后的消息列表

**核心功能：**
- **智能检索**: 基于语义相似度的文档检索
- **上下文融合**: 将检索内容与对话上下文融合
- **答案生成**: 基于检索内容生成准确回答
- **引用支持**: 提供答案来源的文档引用
- **多模态支持**: 支持文本和图片混合检索

### 2. ModelstudioRagLite - 百炼RAG轻量版
提供轻量化的RAG功能，适合资源受限或快速响应的场景。

**前置使用条件：**
- 基本的百炼服务配置
- 较小规模的知识库

**主要特点：**
- 更快的响应速度
- 较低的资源消耗
- 简化的配置选项
- 适合移动端或边缘计算

## 🔧 环境变量配置

| 环境变量 | 必需 | 默认值 | 说明 |
|---------|------|--------|------|
| `DASHSCOPE_API_KEY` | ✅ | - | DashScope API密钥 |
| `DASHSCOPE_HTTP_BASE_URL` | ✅ | - | 百炼服务HTTP基础URL |
| `DEFAULT_KNOWLEDGE_BASE_ID` | ❌ | - | 默认知识库ID |
| `DEFAULT_TOP_K` | ❌ | 5 | 默认检索条目数 |
| `DEFAULT_SCORE_THRESHOLD` | ❌ | 0.7 | 默认相似度阈值 |

## 🚀 使用示例

### 基础RAG查询示例

```python
from agentscope_bricks.components.RAGs.modelstudio_rag import ModelstudioRag
import asyncio

# 初始化RAG组件
rag = ModelstudioRag()


async def rag_query_example():
    result = await rag.arun({
        "messages": [
            {"role": "user", "content": "请介绍一下人工智能的发展历史"}
        ],
        "rag_options": {
            "knowledge_base_id": "kb_12345",
            "top_k": 3,
            "score_threshold": 0.8,
            "enable_citation": True
        },
        "rest_token": "your_auth_token"
    })

    print("RAG回答:", result.rag_result["answer"])
    print("参考文献:", result.rag_result["references"])


asyncio.run(rag_query_example())
```

### 多轮对话RAG示例
```python
async def multi_turn_rag_example():
    conversation_history = [
        {"role": "user", "content": "什么是机器学习？"},
        {"role": "assistant", "content": "机器学习是人工智能的一个重要分支..."},
        {"role": "user", "content": "它有哪些主要类型？"}
    ]

    result = await rag.arun({
        "messages": conversation_history,
        "rag_options": {
            "knowledge_base_id": "kb_ai_encyclopedia",
            "top_k": 5,
            "enable_citation": True
        },
        "rest_token": "your_auth_token"
    })

    print("基于上下文的回答:", result.rag_result["answer"])

asyncio.run(multi_turn_rag_example())
```

### 多模态RAG示例
```python
async def multimodal_rag_example():
    result = await rag.arun({
        "messages": [
            {"role": "user", "content": "请分析这张图片中的技术架构"}
        ],
        "image_urls": [
            "https://example.com/architecture_diagram.png"
        ],
        "rag_options": {
            "knowledge_base_id": "kb_tech_docs",
            "top_k": 3,
            "enable_citation": True
        },
        "rest_token": "your_auth_token"
    })

    print("多模态分析结果:", result.rag_result["answer"])

asyncio.run(multimodal_rag_example())
```

## 🏗️ RAG架构特点

### 检索策略
- **密集检索**: 基于向量相似度的语义检索
- **稀疏检索**: 基于关键词匹配的精确检索
- **混合检索**: 结合密集和稀疏检索的优势
- **重排序**: 对检索结果进行相关性重排序

### 生成策略
- **上下文注入**: 将检索内容注入到生成模型
- **答案合成**: 基于多个文档片段合成答案
- **引用生成**: 自动生成答案的文档引用
- **事实验证**: 对生成答案进行事实性检查

## 📊 性能优化

### 检索优化
- 使用向量索引加速检索（如FAISS、Milvus）
- 实现检索结果缓存
- 优化文档分块和嵌入策略
- 并行处理多个检索请求

### 生成优化
- 设置合理的上下文长度限制
- 使用流式生成提高用户体验
- 实现答案质量评分机制
- 优化模型推理参数

## 📦 依赖包
- `aiohttp`: 异步HTTP客户端
- `dashscope`: DashScope SDK
- `asyncio`: 异步编程支持
- `numpy`: 数值计算（向量操作）
- `faiss`: 向量检索（可选）

## ⚠️ 使用注意事项

### 知识库管理
- 定期更新知识库内容，确保信息时效性
- 合理设计文档分块策略，平衡检索精度和召回率
- 监控知识库的查询性能和命中率
- 建立知识库版本管理机制

### 查询优化
- 设置合适的相似度阈值，避免检索到不相关内容
- 合理配置top_k参数，平衡答案质量和响应速度
- 对长查询进行预处理和优化
- 实现查询意图分析和路由

### 答案质量控制
- 建立答案质量评估机制
- 对生成答案进行事实性检查
- 处理检索结果不足的情况
- 提供答案置信度评分

## 🔗 相关组件
- 可与搜索组件结合，扩展知识来源
- 支持与内存组件集成，提供个性化RAG体验
- 可与意图识别组件配合，实现智能知识问答
- 支持与插件系统集成，扩展RAG功能范围