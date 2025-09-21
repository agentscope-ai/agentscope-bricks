# 内存管理组件 (Memory)

本目录包含各种内存管理和存储组件，提供对话历史管理、内存节点操作和持久化存储功能。

## 📋 组件列表

### 1. Modelstudio Memory 组件集
基于百炼服务的内存管理组件，提供完整的内存操作功能。

#### AddMemory - 添加内存组件
将对话消息存储为内存节点。

**前置使用条件：**
- 配置内存服务端点
- 有效的DashScope API密钥
- 配置百炼服务ID

**主要功能：**
- 存储用户对话消息
- 自动提取关键信息
- 支持标签和分类

#### SearchMemory - 搜索内存组件
基于对话上下文搜索相关内存。

**主要功能：**
- 语义相似度搜索
- 上下文相关性匹配
- 支持多种搜索策略

#### ListMemory - 列举内存组件
列出用户的所有内存节点。

**主要功能：**
- 分页查询内存列表
- 支持时间范围过滤
- 内存节点摘要显示

#### DeleteMemory - 删除内存组件
删除特定的内存节点。

**主要功能：**
- 精确删除指定内存
- 批量删除支持
- 删除确认机制

### 2. LocalMemory - 本地内存管理
提供本地化的内存管理功能，无需外部服务依赖。

**前置使用条件：**
- 本地存储空间
- 读写权限

**输入参数 (MemoryInput)：**
- `operation_type`: 操作类型（添加、搜索、删除等）
- `run_id`: 运行会话ID
- `messages`: 消息列表
- `filters`: 过滤条件

**输出参数 (MemoryOutput)：**
- `infos`: 内存信息列表
- `messages`: 处理后的消息
- `summarization`: 内存摘要

**主要功能：**
- 聊天历史管理
- 会话状态维护
- 本地数据持久化

### 3. RedisMemory - Redis内存存储
基于Redis的高性能内存存储解决方案。

**前置使用条件：**
- Redis服务器运行中
- Redis连接配置
- 适当的Redis权限

**主要功能：**
- 高性能内存操作
- 分布式内存共享
- 自动过期管理
- 数据持久化

## 🔧 环境变量配置

| 环境变量 | 必需 | 默认值 | 说明 |
|---------|------|--------|------|
| `MEMORY_SERVICE_ENDPOINT` | ✅ | - | 内存服务端点URL |
| `MODELSTUDIO_SERVICE_ID` | ✅ | - | 百炼服务ID |
| `DASHSCOPE_API_KEY` | ✅ | - | DashScope API密钥 |
| `REDIS_URL` | ❌ | localhost:6379 | Redis服务器地址（Redis内存） |
| `REDIS_PASSWORD` | ❌ | - | Redis密码（Redis内存） |

## 🚀 使用示例

### 百炼内存管理示例

```python
from agentscope_bricks.components.memory import AddMemory, SearchMemory
import asyncio

# 添加内存
add_memory = AddMemory()
search_memory = SearchMemory()


async def memory_example():
    # 存储对话内容
    add_result = await add_memory.arun({
        "messages": [
            {"role": "user", "content": "我喜欢吃披萨"},
            {"role": "assistant", "content": "好的，我记住了您喜欢披萨"}
        ]
    })

    # 搜索相关内存
    search_result = await search_memory.arun({
        "query": "用户的饮食偏好",
        "top_k": 5
    })
    print("相关内存:", search_result.memories)


asyncio.run(memory_example())
```

### 本地内存管理示例

```python
from agentscope_bricks.components.memory import LocalMemory
import asyncio

# 本地内存管理
local_memory = LocalMemory()


async def local_memory_example():
    # 添加聊天历史
    result = await local_memory.arun({
        "operation_type": "add",
        "run_id": "session_001",
        "messages": [
            {"role": "user", "content": "你好"},
            {"role": "assistant", "content": "您好！有什么可以帮助您的吗？"}
        ]
    })
    print("内存操作结果:", result.infos)


asyncio.run(local_memory_example())
```

## 🏗️ 架构特点

### 内存层次结构
- **短期内存**: 当前会话的对话内容
- **长期内存**: 持久化的用户偏好和历史信息
- **工作内存**: 当前任务相关的临时信息

### 存储策略
- **本地存储**: 适合单机部署，数据隐私性高
- **云端存储**: 适合分布式部署，支持跨设备同步
- **混合存储**: 结合本地和云端优势

## 📦 依赖包
- `aiohttp`: 异步HTTP客户端（云端内存）
- `redis`: Redis客户端（Redis内存）
- `uuid`: 唯一标识符生成
- `SimpleChatStore`: 简单聊天存储（本地内存）

## ⚠️ 使用注意事项

### 数据安全
- 内存中可能包含敏感用户信息，需要加密存储
- 定期清理过期或不需要的内存数据
- 遵循数据保护法规要求

### 性能优化
- 合理设置内存缓存大小，避免内存溢出
- 使用分页查询处理大量历史数据
- 定期优化和压缩存储的内存数据

### 可靠性保障
- 实现内存数据的备份和恢复机制
- 处理网络异常和服务不可用情况
- 提供内存数据的一致性检查

## 🔗 相关组件
- 可与RAG组件结合，提供基于内存的上下文增强
- 支持与意图识别组件集成，实现智能内存检索
- 可与对话管理系统配合，提供连续的对话体验
