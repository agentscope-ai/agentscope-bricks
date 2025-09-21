# Agentic RAG Application

This is an intelligent decision-making RAG application based on the agentbricks framework that can automatically select appropriate processing methods based on user queries and output information from four modules in a structured format:
1. Thinking Module: Model's reasoning process
2. Task List: Execution plan and completion status
3. Web Search Module: Web search results
4. Knowledge Base Retrieval Module: RAG-recalled document chunks

## Features

- **Intelligent Decision Making**: Automatically selects the best processing method based on user query content
- **Multi-turn Conversation**: Supports multi-turn conversation context understanding
- **RAG Integration**: Integrates Bailian RAG components, supporting private knowledge base retrieval
- **Web Search**: Integrates Bailian search components to obtain real-time network information
- **Structured Output**: Structured output in four modules for easy frontend display
- **Detailed Logging**: Console output of detailed processing logs
- **Streaming Response**: Supports streaming output for better user experience

## Prerequisites

Before starting the service, you need to configure the following environment variables:

```bash
export DASHSCOPE_API_KEY=""
```

You also need to have knowledge base pipelines configured in Alibaba Cloud Bailian platform.

## Configuration

### 1. Configure Alibaba Cloud Bailian RAG Knowledge Base

To use the RAG functionality, you need to:

1. Log in to the [Alibaba Cloud Bailian Platform](https://bailian.console.aliyun.com)
2. Create a knowledge base and upload your documents
3. Create a pipeline for your knowledge base
4. Note down the pipeline IDs which will be used in API requests

For detailed instructions on configuring RAG knowledge bases, please refer to the [Alibaba Cloud Bailian RAG Documentation](https://bailian.console.aliyun.com/?tab=doc#/doc/?type=app&url=2807740).

### 2. Environment Variables

Make sure to set the following environment variables:

```bash
export DASHSCOPE_API_KEY=""
```

The `DASHSCOPE_API_KEY` can be obtained from the [DashScope Console](https://dashscope.console.aliyun.com/).

## Starting the Service

```bash
cd demos/agentic_rag
python agentic_rag_service.py
```

The service will start at `http://127.0.0.1:8091`.

## API Usage

### RAG Query Example

Before using the following API, please ensure you have created a knowledge base and obtained pipeline_ids on the Alibaba Cloud Bailian platform. For specific steps, please refer to the "Configure Alibaba Cloud Bailian RAG Knowledge Base" section above.

```bash
curl --location 'http://127.0.0.1:8091/api/v1/chat/completions' \
--header 'Content-Type: application/json' \
--data '{
    "model": "qwen-max",
    "messages": [
        {
            "role": "user",
            "content": "Help me find the brand characteristics of the representative shoe models: The Reynolds, Wino G6 through the knowledge base. If not found, try using search."
        }
    ],
    "rag_options": {
        "pipeline_ids": ["your pipeline_ids"],
        "maximum_allowed_chunk_num": 10
    }
}'
```

Please replace `["your pipeline_ids"]` in the above example with the knowledge base pipeline ID you created on the Alibaba Cloud Bailian platform. You can find detailed instructions on how to create and obtain pipeline IDs in the [Alibaba Cloud Bailian RAG Documentation](https://bailian.console.aliyun.com/?tab=doc#/doc/?type=app&url=2807740).

### General Query Example

```bash
curl --location 'http://127.0.0.1:8091/api/v1/chat/completions' \
--header 'Content-Type: application/json' \
--data '{
    "model": "qwen-max",
    "messages":[
        {"role": "user", "content": "How is the weather today?"}
    ]
}'
```

## Response Format

The API returns structured data in JSON format, containing four modules:

```json
{
  "thinking": {
    "process": "Detailed thinking process..."
  },
  "task_list": {
    "tasks": ["Task 1", "Task 2", "Task 3"],
    "current_task": 1,
    "completed_tasks": [0]
  },
  "search": {
    "query": "Search query",
    "results": [
      {
        "title": "Result title",
        "snippet": "Result summary",
        "url": "Link",
        "hostname": "Domain",
        "hostlogo": "Website icon"
      }
    ],
    "status": 0
  },
  "rag": {
    "query": "RAG query",
    "chunks": [
      {
        "id": 0,
        "content": "Document content",
        "source": "Source",
        "score": 0.95,
        "metadata": {}
      }
    ],
    "status": 0
  },
  "final_response": "Final answer..."
}
```

## Console Log Output

The service outputs detailed processing logs to the console for debugging and monitoring:

```
[Main Service] Starting to process user request
[Main Service] User query: Please help me analyze...
[Main Service] Step 1 - Generate thinking process
[Thinking Module] Starting to generate thinking process: Please help me analyze...
[Thinking Module] Thinking process generation completed
[Main Service] Step 2 - Generate task list
[Task List Module] Starting to generate task list: Please help me analyze...
[Task List Module] Task list generation completed: ['Task 1', 'Task 2', 'Task 3']
[Main Service] Step 3 - Make decision
[Decision Module] Starting to analyze user query: Please help me analyze...
[Decision Module] Decision result: RAG
[Main Service] Step 4 - Execute RAG processing
[RAG Module] Starting to process RAG request
[RAG Module] RAG processing completed, recalled documents: 2
[Main Service] Step 4 - RAG intermediate result output: {...}
[Main Service] Step 5 - Generate final answer
[Main Service] Step 5 - Final result output: {...}
[Main Service] Request processing completed
```

## Frontend Display Suggestions

1. **Thinking Module**: Display the model's thinking process to help users understand the model's reasoning logic
2. **Task List**: Display task execution status in progress bar or list format
3. **Search Module**: Display search results in card format, including title, summary, and links
4. **RAG Module**: Display retrieved document chunks with support for expand/collapse to view detailed content