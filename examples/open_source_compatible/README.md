# Open Source Compatibility Demo

## Quick Start

This demo showcases agentscope-bricks compatibility and integration with popular open-source AI frameworks including LangGraph, AutoGen, AgentScope, and LlamaIndex.

### Available Integrations

#### LangGraph Integration
```shell
python langgraph_example.py
```
Demonstrates agentscope-bricks components as LangGraph nodes with state management and memory.

#### AutoGen Integration
```shell
python autogen_example.py
```
Shows agentscope-bricks components integrated with Microsoft AutoGen multi-agent framework.

#### AgentScope Integration
```shell
python agentscope_example.py
```
Example of agentscope-bricks components working within AgentScope agent orchestration.

#### LlamaIndex Integration
```shell
python llama_index_example.py
```
Integration with LlamaIndex for advanced RAG and document processing workflows.

### Setup

1. Install framework dependencies:
```shell
pip install langgraph langchain-openai
pip install pyautogen
pip install agentscope
pip install llama-index
```

2. Set up environment:
```shell
export DASHSCOPE_API_KEY=your_api_key
export PYTHONPATH=$PYTHONPATH:/path/to/agentscope-bricks/project
```

### Framework Adapters

#### LangGraph Adapter
```python
from agentscope-bricks.langgraph_util import LanggraphNodeAdapter
node = LanggraphNodeAdapter(your_component)
```

#### AutoGen Adapter
```python
from agentscope-bricks.autogen_util import AutogenToolAdapter
tool = AutogenToolAdapter(your_component)
```

#### AgentScope Runtime
```python
# Direct component usage in AgentScope workflows
```

### Features

- **Universal Component Interface**: Use agentscope-bricks components across multiple frameworks
- **State Management**: Framework-native state handling and persistence
- **Tool Adaptation**: Automatic tool schema generation and validation
- **Memory Integration**: Compatible with framework-specific memory systems
- **Async Support**: Full asynchronous operation across all integrations

### Architecture Benefits

- **Framework Agnostic**: Write once, run anywhere approach
- **Type Safety**: Maintains Pydantic validation across frameworks
- **Observability**: Consistent tracing and monitoring
- **Modularity**: Easy component swapping between frameworks

### Use Cases

- Multi-framework development and testing
- Framework migration and comparison
- Hybrid agent system architectures
- Component reusability across projects
- Open-source ecosystem integration