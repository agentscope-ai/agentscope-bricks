# AgentScope Runtime 集成示例

本示例演示了如何使用 **agentscope-bricks** 来辅助 Agent 开发，并利用 **agentscope-runtime** 进行调试和部署。

## 🎯 项目概述

本项目演示了三种不同类型的 Agent 实现：
1. **AgentScope Agent** - 基于 AgentScope 框架的 ReAct Agent
2. **LangGraph Agent** - 基于 LangGraph 的工作流 Agent
3. **Custom Agent** - 基于 agentscope-bricks 的简单 Agent

所有 Agent 都集成了 agentscope-bricks 提供的搜索组件，并可以通过 agentscope-runtime 进行统一的调试和部署。

## 🚀 快速开始

### 环境设置

1. **安装依赖**
```bash
pip install agentscope-bricks agentscope-runtime
```

2. **配置 API Key**
```bash
export DASHSCOPE_API_KEY=""
```

### 开发和调试

运行开发调试脚本来测试 Agent 功能：

```bash
python agent_development.py
```

选择要测试的 Agent 类型：
- `1` - AgentScope Agent
- `2` - LangGraph Agent
- `3` - Custom Agent

### 服务部署

运行部署脚本将 Agent 部署为 HTTP 服务：

```bash
python agent_deployment.py
```

服务启动后，可以按如下方式调用：

```bash
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
```

## 🛠️ AgentScope-Bricks 组件使用

### 搜索组件

所有 Agent 都集成了 `ModelstudioSearchLite` 搜索组件：

```python
from agentscope_bricks.components.searches.modelstudio_search_lite import ModelstudioSearchLite

# 创建搜索工具
search_tool = ModelstudioSearchLite()
```

### 适配器

不同框架需要相应的适配器：

```python
# AgentScope Runtime 适配器
from agentscope_bricks.adapters.agentscope_runtime.tool import AgentScopeRuntimeToolAdapter
tool = AgentScopeRuntimeToolAdapter(search_tool)

# LangGraph 适配器
from agentscope_bricks.adapters.langgraph.tool import LanggraphNodeAdapter
tool_node = LanggraphNodeAdapter([search_tool])
```

### Agent API

这些演示继承自 AgentScope-Runtime 基础 Agent 类，接收精心设计的 agent 请求，
并返回相应的响应，以便用户部署服务时能返回合理的结果。
这种精心设计的请求-响应协议被称为 **Agent API**

Agent API 的详细信息可以参考 [customize_agent](react_agent_with_customize_agent.py)


## 🔍 AgentScope-Runtime 功能

### 开发和调试

`agent_developement.py` 提供了简单的调试接口：

```python
async def simple_call_agent_direct(agent, query):
    async with create_context_manager() as context_manager:
        runner = Runner(agent=agent, context_manager=context_manager)
        result = await simple_call_agent(query, runner)
    return result
```

### 服务部署

`agent_deployment.py` 提供了完整的部署功能：

```python
# 创建运行器
async with create_runner(agent) as runner:
    # 部署为 HTTP 服务
    deploy_manager = LocalDeployManager(host="localhost", port=8090)
    deploy_result = await runner.deploy(
        deploy_manager=deploy_manager,
        endpoint_path="/process",
        stream=True,
    )
```
然后用户可以通过简化的 agent api 查询 agent：

```shell
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
```

### 高级部署

添加响应 API 接口

```python
from agentscope_runtime.engine.deployers.adapter.responses.response_api_protocol_adapter import ResponseAPIDefaultAdapter   # noqa E501

async with create_runner(agent) as runner:
    # 部署为 HTTP 服务
    deploy_manager = LocalDeployManager(host="localhost", port=8090)
    deploy_result = await runner.deploy(
        deploy_manager=deploy_manager,
        endpoint_path="/process",
        stream=True,
        protocol_adapters=[ResponseAPIDefaultAdapter()],
    )
```
添加响应 API 协议适配器后，用户可以通过响应 API 查询 agent。

```python
from openai import OpenAI, AsyncOpenAI
import openai

api_url = 'http://0.0.0.0:8090/compatible-mode/v1'
openai.api_base = api_url
openai.api_key = ''

openai_client = OpenAI(
                api_key='',
                base_url=api_url,
            )

response = openai_client.responses.create(
    model='gpt-4',
    input=[{
        'role': 'user',
        'content': '给我讲一个关于机器人学跳舞的短故事。',
    }],
    stream=True,
)
event_count = 0
for event in response:
    event_count += 1
    event_type = event.type if hasattr(event, 'type') else 'unknown'
    print(f'   PACKAGE event {event_count}: {event_type}')

    # 打印事件详情
    if hasattr(event, 'id'):
        print(f'      ID: {event.id}')
    if hasattr(event, 'created_at'):
        print(f'      created: {event.created_at}')
    if hasattr(event, 'model'):
        print(f'      model: {event.model}')

    # 打印内容相关字段
    content_fields = ['content', 'text', 'item', 'output']
    for field in content_fields:
        if hasattr(event, field):
            value = getattr(event, field)
            if value:
                print(f'      {field}: {value}')

print(f'   SUCCESS streaming response, total:  {event_count} events')
```

### 核心功能

- **会话管理**：支持多用户多会话
- **流式响应**：支持实时流式输出
- **工具调用**：统一的工具调用接口
- **环境管理**：沙盒环境支持
- **健康检查**：内置健康检查端点

## 📝 使用场景

1. **快速原型开发**：使用 agentscope-bricks 快速构建 Agent 原型
2. **多框架集成**：支持 AgentScope、LangGraph 等多种框架
3. **生产部署**：通过 agentscope-runtime 部署为生产服务
4. **调试和测试**：提供完整的调试和测试工具
