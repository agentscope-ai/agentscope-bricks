## 快速开始

本示例为多模态视频生成，流程如下：

![流程图](assets/flow.png)

### 设置环境变量
```shell

# 百炼平台API-Key
DASHSCOPE_API_KEY={your_api_key}

# 阿里云OSS配置
OSS_ACCESS_KEY_ID={your_ak}
OSS_ACCESS_KEY_SECRET={your_sk}
OSS_ENDPOINT={your_endpoint}
OSS_BUCKET={your_bucket}
OSS_DIRECTORY={your_directory}

# 可观测相关配置
TRACE_ENABLE_LOG=1
TRACE_ENABLE_REPORT=0
TRACE_ENABLE_DEBUG=0
```


### 启动服务端
```shell
export PYTHONPATH=$(pwd):$PYTHONPATH && python demos/multimodal_generation/backend/app.py
```

### 启动客户端
```shell
export PYTHONPATH=$(pwd):$PYTHONPATH && python demos/multimodal_generation/backend/test/agent_api_client.py
```





