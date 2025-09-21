# Memory Management Components

This directory contains various memory management and storage components, providing conversation history management, memory node operations, and persistent storage functionality.

## 📋 Component List

### 1. Modelstudio Memory Component Suite
Memory management components based on Bailian services, providing complete memory operation functionality.

#### AddMemory - Add Memory Component
Stores conversation messages as memory nodes.

**Prerequisites:**
- Configure memory service endpoint
- Valid DashScope API key
- Configure Bailian service ID

**Main Features:**
- Store user conversation messages
- Automatically extract key information
- Support tags and categorization

#### SearchMemory - Search Memory Component
Search relevant memories based on conversation context.

**Main Features:**
- Semantic similarity search
- Context relevance matching
- Support multiple search strategies

#### ListMemory - List Memory Component
List all memory nodes for a user.

**Main Features:**
- Paginated memory list queries
- Support time range filtering
- Memory node summary display

#### DeleteMemory - Delete Memory Component
Delete specific memory nodes.

**Main Features:**
- Precise deletion of specified memories
- Batch deletion support
- Deletion confirmation mechanism

### 2. LocalMemory - Local Memory Management
Provides localized memory management functionality without external service dependencies.

**Prerequisites:**
- Local storage space
- Read/write permissions

**Input Parameters (MemoryInput):**
- `operation_type`: Operation type (add, search, delete, etc.)
- `run_id`: Runtime session ID
- `messages`: Message list
- `filters`: Filter conditions

**Output Parameters (MemoryOutput):**
- `infos`: Memory information list
- `messages`: Processed messages
- `summarization`: Memory summary

**Main Features:**
- Chat history management
- Session state maintenance
- Local data persistence

### 3. RedisMemory - Redis Memory Storage
High-performance memory storage solution based on Redis.

**Prerequisites:**
- Redis server running
- Redis connection configuration
- Appropriate Redis permissions

**Main Features:**
- High-performance memory operations
- Distributed memory sharing
- Automatic expiration management
- Data persistence

## 🔧 Environment Variable Configuration

| Environment Variable | Required | Default Value | Description |
|---------------------|----------|---------------|-------------|
| `MEMORY_SERVICE_ENDPOINT` | ✅ | - | Memory service endpoint URL |
| `MODELSTUDIO_SERVICE_ID` | ✅ | - | Bailian service ID |
| `DASHSCOPE_API_KEY` | ✅ | - | DashScope API key |
| `REDIS_URL` | ❌ | localhost:6379 | Redis server address (Redis memory) |
| `REDIS_PASSWORD` | ❌ | - | Redis password (Redis memory) |

## 🚀 Usage Examples

### Bailian Memory Management Example

```python
from agentscope_bricks.components.memory import AddMemory, SearchMemory
import asyncio

# Add memory
add_memory = AddMemory()
search_memory = SearchMemory()


async def memory_example():
    # Store conversation content
    add_result = await add_memory.arun({
        "messages": [
            {"role": "user", "content": "I like eating pizza"},
            {"role": "assistant", "content": "Got it, I'll remember that you like pizza"}
        ]
    })

    # Search relevant memories
    search_result = await search_memory.arun({
        "query": "user's food preferences",
        "top_k": 5
    })
    print("Relevant memories:", search_result.memories)


asyncio.run(memory_example())
```

### Local Memory Management Example

```python
from agentscope_bricks.components.memory import LocalMemory
import asyncio

# Local memory management
local_memory = LocalMemory()


async def local_memory_example():
    # Add chat history
    result = await local_memory.arun({
        "operation_type": "add",
        "run_id": "session_001",
        "messages": [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hello! How can I help you?"}
        ]
    })
    print("Memory operation result:", result.infos)


asyncio.run(local_memory_example())
```

## 🏗️ Architecture Features

### Memory Hierarchy
- **Short-term Memory**: Current session conversation content
- **Long-term Memory**: Persistent user preferences and historical information
- **Working Memory**: Temporary information related to current tasks

### Storage Strategies
- **Local Storage**: Suitable for single-machine deployment, high data privacy
- **Cloud Storage**: Suitable for distributed deployment, supports cross-device synchronization
- **Hybrid Storage**: Combines advantages of local and cloud storage

## 📦 Dependencies
- `aiohttp`: Async HTTP client (cloud memory)
- `redis`: Redis client (Redis memory)
- `uuid`: Unique identifier generation
- `SimpleChatStore`: Simple chat storage (local memory)

## ⚠️ Usage Notes

### Data Security
- Memory may contain sensitive user information, requires encrypted storage
- Regularly clean expired or unnecessary memory data
- Comply with data protection regulations

### Performance Optimization
- Set reasonable memory cache sizes to avoid memory overflow
- Use paginated queries to handle large amounts of historical data
- Regularly optimize and compress stored memory data

### Reliability Assurance
- Implement backup and recovery mechanisms for memory data
- Handle network exceptions and service unavailability
- Provide consistency checks for memory data

## 🔗 Related Components
- Can be combined with RAG components to provide memory-based context enhancement
- Supports integration with intent recognition components for intelligent memory retrieval
- Can work with conversation management systems to provide continuous conversation experience
