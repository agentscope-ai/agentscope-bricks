## Quick Start

This example demonstrates multimodal video generation with the following workflow:

![Workflow](assets/flow.png)

### Environment Variables Setup
```shell

# ModelStudio Platform API-Key
DASHSCOPE_API_KEY={your_api_key}

# Alibaba Cloud OSS Configuration
OSS_ACCESS_KEY_ID={your_ak}
OSS_ACCESS_KEY_SECRET={your_sk}
OSS_ENDPOINT={your_endpoint}
OSS_BUCKET={your_bucket}
OSS_DIRECTORY={your_directory}

# Observability Configuration
TRACE_ENABLE_LOG=1
TRACE_ENABLE_REPORT=0
TRACE_ENABLE_DEBUG=0
```


### Start the Server
```shell
export PYTHONPATH=$(pwd):$PYTHONPATH && python demos/multimodal_generation/backend/app.py
```

### Start the Client
```shell
export PYTHONPATH=$(pwd):$PYTHONPATH && python demos/multimodal_generation/backend/test/agent_api_client.py
```




