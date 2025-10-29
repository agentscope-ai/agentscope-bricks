# Multimodal Video Generation Demo

## Project Overview

This demo is a multimodal video generation system that automatically creates complete e-commerce advertising short videos based on user-input product themes. The system adopts a multi-stage pipeline architecture and leverages various AI capabilities including large language models, text-to-image, image-to-video, and text-to-speech to achieve fully automated generation from creative scripts to finished videos.

## Key Features

- **Intelligent Intent Recognition**: Automatically identifies user input intent, supporting multiple commands such as script generation, storyboard design, and character creation
- **Multi-Stage Pipeline**: Includes 12 processing stages covering the complete workflow from script creation to video synthesis
- **Multimodal Generation Capabilities**:
  - Text Generation: Generates creative scripts, storyboard descriptions, and character descriptions using the qwen-max model
  - Image Generation: Creates character images and first-frame images using the wan2.2-t2i-plus model
  - Video Generation: Implements image-to-video conversion based on the wan2.2-i2v-plus model
  - Speech Synthesis: Generates voiceovers using the qwen-tts model
  - Video Synthesis: Automatically synthesizes video clips and adds subtitles
- **Flexible Session Management**: Supports multi-turn conversations, allowing script and storyboard modifications or regeneration at any time
- **Streaming Response**: Supports streaming output to display generation progress in real-time

## System Architecture

### Processing Flow

![Flow Diagram](assets/multimodal_generation_flow.png)

The system includes the following 12 processing stages:

1. **Topic (Theme Input)**: Receives user-input product theme or requirements
2. **Script (Script Generation)**: Generates creative scripts for e-commerce advertisements
3. **Storyboard (Storyboard Design)**: Breaks down the script into multiple scenes
4. **RoleDescription (Character Description)**: Generates detailed character descriptions
5. **RoleImage (Character Image)**: Creates character images based on character descriptions
6. **FirstFrameDescription (First Frame Description)**: Generates first frame descriptions for each scene
7. **FirstFrameImage (First Frame Image)**: Generates first frame images for each scene
8. **VideoDescription (Video Description)**: Generates camera movement descriptions required for video generation
9. **Video (Video Generation)**: Generates video clips based on first frame images and scene descriptions
10. **Line (Dialogue Generation)**: Generates character dialogues for each scene
11. **Audio (Speech Synthesis)**: Converts dialogues into speech
12. **Film (Video Synthesis)**: Synthesizes all video clips, adds subtitles and voiceovers

### Core Components

- **FilmAgent**: Main control agent responsible for coordinating the entire generation process
- **Classifier**: Intent classifier that identifies user commands and determines which stage to execute
- **StageSession**: Session manager that maintains generation results for each stage
- **Handler**: Stage processors responsible for specific generation tasks

## Quick Start

### Environment Requirements

- Python 3.10+
- Bailian Platform API Key
- Alibaba Cloud OSS (for storing generated images and videos)

### Setting Environment Variables

Configure the following environment variables:

```shell
# Bailian Platform API Key
DASHSCOPE_API_KEY={your_api_key}

# Alibaba Cloud OSS Configuration
OSS_ACCESS_KEY_ID={your_ak}
OSS_ACCESS_KEY_SECRET={your_sk}
OSS_ENDPOINT={your_endpoint}
OSS_BUCKET={your_bucket}
OSS_DIRECTORY={your_directory}
```

### Installing Dependencies

Navigate to the project root directory and install required dependencies:

```shell
pip install -e .
pip install -r demos/multimodal_generation/backend/requirements.txt
```

Main dependencies include:
- `agentscope-runtime`: AgentScope Runtime framework
- `moviepy`: Video editing and processing
- `oss2`: Alibaba Cloud OSS SDK

### Configuring Backend Service

The configuration file is located at `backend/config.json`, where you can adjust the models and parameters used in each stage:

```json
{
    "intent": {
        "model": "qwen-max"
    },
    "script": {
        "model": "qwen-max",
        "t2i_model": "wan2.2-t2i-plus",
        "vl_model": "qvq-max"
    },
    "storyboard": {
        "model": "qwen-max",
        "max_boards": 2,
        "max_roles": 2
    },
    "role_image": {
        "model": "wan2.2-t2i-plus",
        "rps": 2
    },
    "video": {
        "model": "wan2.2-i2v-plus",
        "rps": 2
    },
    "audio": {
        "model": "qwen-tts"
    },
    "film": {
        "font_size": 60,
        "font_color": "white",
        "fadein_duration": 0.5
    }
}
```

### Running Test Cases

#### Method 1: Start Backend as a Service

```shell
cd agentscope-bricks
export PYTHONPATH=$(pwd):$PYTHONPATH
python demos/multimodal_generation/backend/app.py
```

After the service starts, it listens on `http://0.0.0.0:8080` by default

Start the client:

```bash
export PYTHONPATH=$(pwd):$PYTHONPATH
python demos/multimodal_generation/backend/test/agent_api_client.py
```

Example log of the final result received by the client:
```json
{
    "sequence_number": 1,
    "object": "response",
    "status": "completed",
    "error": null,
    "id": "response_6f1713c2-4631-432c-8e84-22d78e5e6bfb",
    "created_at": 1761701161,
    "completed_at": null,
    "output": [
        {
            "sequence_number": 0,
            "object": "message",
            "status": "completed",
            "error": null,
            "id": "msg_8ae0b947-43af-41ee-bb9d-c476415b6329",
            "type": "message",
            "role": "assistant",
            "content": [
                {
                    "sequence_number": null,
                    "object": "content",
                    "status": "completed",
                    "error": null,
                    "type": "data",
                    "index": 0,
                    "delta": false,
                    "msg_id": "msg_8ae0b947-43af-41ee-bb9d-c476415b6329",
                    "data": {
                        "video_url": "https://bailian-cn-beijing.oss-cn-beijing.aliyuncs.com/multimodal_generation%2Fmock_session_id%2Ffilm.mp4?OSSAccessKeyId=LTAI5tSr8GHZekwmKPw28SMf&Expires=1761707925&Signature=wHKTKJlHy2nZB4ZHxAwvf2uVHuY%3D"
                    }
                }
            ],
            "code": null,
            "message": null,
            "usage": null
        }
    ],
    "usage": null,
    "session_id": null
}
```

#### Method 2: Test Backend Program Only

```shell
cd agentscope-bricks
export PYTHONPATH=$(pwd):$PYTHONPATH
python demos/multimodal_generation/backend/test/utils.py
```

Example log of the final result printed by the backend:
```json
{
    "time": "2025-10-29 10:38:07.242",
    "step": "film_stage_end",
    "model": "",
    "user_id": "",
    "code": "",
    "message": "",
    "task_id": "",
    "request_id": "f67c883a-1e2b-48e8-a319-cf9fd0ec19cc",
    "context": {
        "sequence_number": null,
        "object": "message",
        "status": "completed",
        "error": null,
        "id": "msg_eea15b5e-9b01-4d86-a894-a9f943df7894",
        "type": "message",
        "role": "assistant",
        "content": [
            {
                "sequence_number": null,
                "object": "content",
                "status": "completed",
                "error": null,
                "type": "data",
                "index": 0,
                "delta": false,
                "msg_id": "msg_eea15b5e-9b01-4d86-a894-a9f943df7894",
                "data": {
                    "video_url": "https://bailian-cn-beijing.oss-cn-beijing.aliyuncs.com/multimodal_generation%2Fmock_session_id%2Ffilm.mp4?OSSAccessKeyId=LTAI5tSr8GHZekwmKPw28SMf&Expires=1761709087&Signature=4cDl6Kq94RYalKDUBrxljRi0qtA%3D"
                }
            }
        ],
        "code": null,
        "message": null,
        "usage": null
    },
    "interval": {
        "type": "film_stage_end",
        "cost": "28.779"
    },
    "ds_service_id": "test_id",
    "ds_service_name": "test_name"
}
```



## Important Notes

1. **Resource Consumption**: Generating a complete video requires calling multiple AI models and may take a considerable amount of time (several minutes to over ten minutes)
2. **Cost Control**: Image generation, video generation, and speech synthesis all incur API call fees
3. **OSS Storage**: Generated images and videos will be uploaded to OSS, please ensure sufficient storage space
4. **Network Requirements**: A stable network connection is required to call the Bailian Platform API
5. **Session Management**: Currently uses in-memory storage for sessions; session data will be lost after service restart
