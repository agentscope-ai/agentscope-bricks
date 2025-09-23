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
```

进入项目根目录

### 安装依赖

```shell
pip install -r demos/multimodal_generation/backend/requirements.txt
```

### 运行程序
```shell
export PYTHONPATH=$(pwd):$PYTHONPATH && python demos/multimodal_generation/backend/test/utils.py
```