# Components Demo

## Quick Start

This examples provides  of using various AgentScope-Bricks components in different scenarios.

### Available Examples

#### Core Components
- `llm_service.py` - Basic LLM service implementation with streaming support
- `create_component.py` - Component creation and configuration examples

#### Advanced Integration
- `rag_with_llm.py` - RAG with LLM call
- `search_with_llm.py` - Search components with LLM processing

### Running the Examples

1. Set up environment:
```shell
export DASHSCOPE_API_KEY=your_api_key
export PYTHONPATH=$PYTHONPATH:/path/to/agentscope-bricks/project
```

2. Run individual examples:
```shell
python llm_service.py          # Basic LLM streaming service
python rag_with_llm.py         # RAG with LLM
python search_with_llm.py      # Search with LLM
```
