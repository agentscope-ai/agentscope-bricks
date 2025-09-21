# 智能体RAG应用

这是一个基于agentbricks框架的智能决策RAG应用，能够根据用户查询自动选择合适的处理方式，并以结构化格式输出四个模块的信息：
1. 思考模块：模型的推理过程
2. 任务列表：执行计划和完成状态
3. 网络搜索模块：网络搜索结果
4. 知识库检索模块：RAG召回的文档片段

## 功能特性

- **智能决策**：根据用户查询内容自动选择最佳处理方式
- **多轮对话**：支持多轮对话上下文理解
- **RAG集成**：集成百炼RAG组件，支持私有知识库检索
- **网络搜索**：集成百炼搜索组件，获取实时网络信息
- **结构化输出**：四个模块的结构化输出，便于前端展示
- **详细日志**：控制台输出详细处理日志
- **流式响应**：支持流式输出，提升用户体验

## 前置条件

启动服务前，您需要配置以下环境变量：

```bash
export DASHSCOPE_API_KEY=""
```

您还需要在阿里云百炼平台配置知识库流水线。

## 配置说明

### 1. 配置阿里云百炼RAG知识库

要使用RAG功能，您需要：

1. 登录[阿里云百炼平台](https://bailian.console.aliyun.com)
2. 创建知识库并上传文档
3. 为知识库创建流水线
4. 记录流水线ID，将在API请求中使用

有关配置RAG知识库的详细说明，请参考[阿里云百炼RAG文档](https://bailian.console.aliyun.com/?tab=doc#/doc/?type=app&url=2807740)。

### 2. 环境变量配置

请确保设置以下环境变量：

```bash
export DASHSCOPE_API_KEY=""
```

`DASHSCOPE_API_KEY` 可从 [DashScope控制台](https://dashscope.console.aliyun.com/) 获取。

## 启动服务

```bash
cd demos/agentic_rag
python agentic_rag_service.py
```

服务将在 `http://127.0.0.1:8091` 启动。

## API使用示例

### RAG查询示例

在使用以下API之前，请确保您已经在阿里云百炼平台创建了知识库并获取了pipeline_ids。具体步骤请参考前文的"配置阿里云百炼RAG知识库"部分。

```bash
curl --location 'http://127.0.0.1:8091/api/v1/chat/completions' \
--header 'Content-Type: application/json' \
--data '{
    "model": "qwen-max",
    "messages": [
        {
            "role": "user",
            "content": "帮我通过知识库找一下代表鞋款：The Reynolds, Wino G6的品牌特性，如果找不到的话可以试试看使用搜索"
        }
    ],
    "rag_options": {
        "pipeline_ids": ["your pipeline_ids"],
        "maximum_allowed_chunk_num": 10
    }
}'
```

请将上述示例中的`["your pipeline_ids"]`替换为您在阿里云百炼平台创建的知识库pipeline ID。您可以在[阿里云百炼RAG文档](https://bailian.console.aliyun.com/?tab=doc#/doc/?type=app&url=2807740)中找到如何创建和获取pipeline ID的详细说明。

### 通用查询示例

```bash
curl --location 'http://127.0.0.1:8091/api/v1/chat/completions' \
--header 'Content-Type: application/json' \
--data '{
    "model": "qwen-max",
    "messages":[
        {"role": "user", "content": "今天天气怎么样？"}
    ]
}'
```

## 响应格式

API以JSON格式返回结构化数据，包含四个模块：

```json
{
  "thinking": {
    "process": "详细的思考过程..."
  },
  "task_list": {
    "tasks": ["任务1", "任务2", "任务3"],
    "current_task": 1,
    "completed_tasks": [0]
  },
  "search": {
    "query": "搜索查询",
    "results": [
      {
        "title": "结果标题",
        "snippet": "结果摘要",
        "url": "链接",
        "hostname": "域名",
        "hostlogo": "网站图标"
      }
    ],
    "status": 0
  },
  "rag": {
    "query": "RAG查询",
    "chunks": [
      {
        "id": 0,
        "content": "文档内容",
        "source": "来源",
        "score": 0.95,
        "metadata": {}
      }
    ],
    "status": 0
  },
  "final_response": "最终回答..."
}
```

## 控制台日志输出

服务会在控制台输出详细处理日志，便于调试和监控：

```
[主服务] 开始处理用户请求
[主服务] 用户查询: 请帮我分析...
[主服务] 步骤1 - 生成思考过程
[思考模块] 开始生成思考过程: 请帮我分析...
[思考模块] 思考过程生成完成
[主服务] 步骤2 - 生成任务列表
[任务列表模块] 开始生成任务列表: 请帮我分析...
[任务列表模块] 任务列表生成完成: ['任务1', '任务2', '任务3']
[主服务] 步骤3 - 做出决策
[决策模块] 开始分析用户查询: 请帮我分析...
[决策模块] 决策结果: RAG
[主服务] 步骤4 - 执行RAG处理
[RAG模块] 开始处理RAG请求
[RAG模块] RAG处理完成，召回文档: 2
[主服务] 步骤4 - RAG中间结果输出: {...}
[主服务] 步骤5 - 生成最终回答
[主服务] 步骤5 - 最终结果输出: {...}
[主服务] 请求处理完成
```

## 前端展示建议

1. **思考模块**：展示模型的思考过程，帮助用户理解模型的推理逻辑
2. **任务列表**：以进度条或列表形式展示任务执行状态
3. **搜索模块**：以卡片形式展示搜索结果，包括标题、摘要和链接
4. **RAG模块**：展示检索到的文档片段，支持展开/折叠查看详细内容