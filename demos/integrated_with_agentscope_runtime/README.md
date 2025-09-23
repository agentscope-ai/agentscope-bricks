# AgentScope Runtime Integration Examples

This example demonstrates how to use **agentscope-bricks** to assist in Agent development and leverage **agentscope-runtime** for debugging and deployment.

## 🎯 Project Overview

This project demonstrates three different types of Agent implementations:
1. **AgentScope Agent** - ReAct Agent based on AgentScope framework
2. **LangGraph Agent** - Workflow Agent based on LangGraph
3. **Custom Agent** - Simple Agent based on agentscope-bricks

All Agents integrate search components provided by agentscope-bricks and can be uniformly debugged and deployed through agentscope-runtime.

## 🚀 Quick Start

### Environment Setup

1. **Install Dependencies**
```bash
pip install agentscope-bricks agentscope-runtime
```

2. **Configure API Key**
```bash
export DASHSCOPE_API_KEY=""
```

### Development and Debugging

Run the development debugging script to test Agent functionality:

```bash
python agent_development.py
```

Choose the Agent type to test:
- `1` - AgentScope Agent
- `2` - LangGraph Agent
- `3` - Custom Agent

### Service Deployment

Run the deployment script to deploy Agent as an HTTP service:

```bash
python agent_deployment.py
```

After the service starts, you can call it as follows:

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
                    "text": "Where is Hangzhou?"
                }
            ]
        }
    ]
}'
```

## 🛠️ AgentScope-Bricks Component Usage

### Search Component

All Agents integrate the `ModelstudioSearchLite` search component:

```python
from agentscope_bricks.components.searches.modelstudio_search_lite import ModelstudioSearchLite

# Create search tool
search_tool = ModelstudioSearchLite()
```

### Adapters

Different frameworks require corresponding adapters:

```python
# AgentScope Runtime Adapter
from agentscope_bricks.adapters.agentscope_runtime.tool import AgentScopeRuntimeToolAdapter
tool = AgentScopeRuntimeToolAdapter(search_tool)

# LangGraph Adapter
from agentscope_bricks.adapters.langgraph.tool import LanggraphNodeAdapter
tool_node = LanggraphNodeAdapter([search_tool])
```

### Agent API

The demos are inherit from AgentScope-Runtime basic Agent class, which receive an fine-designed agent request,
and thus return a correspond response, so that when user deploy the service, it will return a reasonable result.
This fine designed  request-response protocol are so-called **Agent API**

The detail information of the Agent API could refer the [customize_agent](react_agent_with_customize_agent.py)


## 🔍 AgentScope-Runtime Features

### Development and Debugging

`agent_developement.py` provides a simple debugging interface:

```python
async def simple_call_agent_direct(agent, query):
    async with create_context_manager() as context_manager:
        runner = Runner(agent=agent, context_manager=context_manager)
        result = await simple_call_agent(query, runner)
    return result
```

### Service Deployment

`agent_deployment.py` provides complete deployment functionality:

```python
# Create runner
async with create_runner(agent) as runner:
    # Deploy as HTTP service
    deploy_manager = LocalDeployManager(host="localhost", port=8090)
    deploy_result = await runner.deploy(
        deploy_manager=deploy_manager,
        endpoint_path="/process",
        stream=True,
    )
```
then user could query the agent with a simplified agent api by :

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
                    "text": "Where is Hangzhou?"
                }
            ]
        }
    ]
}'
```

### Advanced Deployment

add response api interface

```python
from agentscope_runtime.engine.deployers.adapter.responses.response_api_protocol_adapter import ResponseAPIDefaultAdapter   # noqa E501

async with create_runner(agent) as runner:
    # Deploy as HTTP service
    deploy_manager = LocalDeployManager(host="localhost", port=8090)
    deploy_result = await runner.deploy(
        deploy_manager=deploy_manager,
        endpoint_path="/process",
        stream=True,
        protocol_adapters=[ResponseAPIDefaultAdapter()],
    )
```
after add the response api protocol adapters, user could query the agent by response api.

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
        'content': 'Tell me a short story about a robot learning to dance.',
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

### Core Features

- **Session Management**: Supports multi-user multi-session
- **Streaming Response**: Supports real-time streaming output
- **Tool Calling**: Unified tool calling interface
- **Environment Management**: Sandbox environment support
- **Health Check**: Built-in health check endpoint

## 📝 Use Cases

1. **Rapid Prototyping**: Use agentscope-bricks to quickly build Agent prototypes
2. **Multi-Framework Integration**: Support multiple frameworks like AgentScope, LangGraph, etc.
3. **Production Deployment**: Deploy as production services through agentscope-runtime
4. **Debugging and Testing**: Provide complete debugging and testing tools
