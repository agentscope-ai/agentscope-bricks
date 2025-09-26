## Quick Start

This example demonstrates multimodal video generation with the following workflow:

![Workflow](assets/flow.png)

### Set Environment Variables
```shell
# ModelStudio Platform API Key
DASHSCOPE_API_KEY={your_api_key}

# Alibaba Cloud OSS Configuration
OSS_ACCESS_KEY_ID={your_ak}
OSS_ACCESS_KEY_SECRET={your_sk}
OSS_ENDPOINT={your_endpoint}
OSS_BUCKET={your_bucket}
OSS_DIRECTORY={your_directory}
```

Navigate to the project root directory

### Install Dependencies

```shell
pip install -r demos/multimodal_generation/backend/requirements.txt
```

### Run the Program
```shell
export PYTHONPATH=$(pwd):$PYTHONPATH && python demos/multimodal_generation/backend/test/utils.py
```
