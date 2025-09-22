# Computer Use Agent Basic Version 🤖

## Chapter 1: Overview

Computer Use Agent is an AI-based desktop automation system that can control the computer to perform various tasks through natural language instructions. The system combines computer vision, natural language processing, and desktop automation technologies, allowing users to complete complex desktop operations with simple Chinese descriptions.

### 🌟 Key Features

- **Intelligent Visual Understanding**: Uses Qwen vision model to understand screen content and accurately locate UI elements
- **Natural Language Interaction**: Supports Chinese natural language instructions without programming knowledge
- **Multiple Operation Support**:
  - Mouse operations (click, double-click, right-click)
  - Keyboard input (text input, shortcuts)
  - System command execution
  - Screen capture and analysis
- **Real-time Monitoring**: Provides complete operation logs and real-time interface feedback
- **Sandbox Environment**: Based on E2B sandbox, Wuying Cloud Computer, Wuying Cloud Phone desktop sandbox, secure isolated execution environment, supports manual intervention operations

### 🏗️ System Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Frontend UI   │◄──►│   Backend API   │◄──►│   AI Agent App  │
│  (Streamlit)    │    │   (FastAPI)     │    │ (GuiAgent)      │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                                        │
                                                        ▼
                                              ┌─────────────────┐
                                              │ E2B Sandbox,    │
                                              │ Wuying          │
                                              │ (Desktop Env)   │
                                              └─────────────────┘
```


### 🔧 Technology Stack

- **Frontend**: Streamlit - Modern Web Interface
- **Backend**: FastAPI - High-performance asynchronous API service
- **Agent Service**:
  - Gui Agent
- **AI Models**:
  - Qwen-VL-Max: Visual understanding and GUI positioning
  - Qwen-Max: Task planning and decision making
- **Automation**: E2B Desktop - Secure desktop sandbox environment
- **Image Processing**: Pillow - Screen capture and image annotation

## Chapter 2: Basic Version Usage

### Qwen-Max + Qwen-VL-MAX + E2B Desktop Integration Usage
Note:
  - Activate DASHSCOPE_API_KEY
  - Activate E2B
  - E2B currently only supports English queries
#### 1. Local Service Startup Preparation
Python needs to be installed in advance, version 3.10 recommended
##### 1.1 Environment Variable Configuration

##### 1.1.1 DashScope Platform Large Model API-KEY Activation
    Documentation:
    https://help.aliyun.com/zh/model-studio/get-api-key?scm=20140722.S_help%40%40%E6%96%87%E6%A1%A3%40%402712195._.ID_help%40%40%E6%96%87%E6%A1%A3%40%402712195-RL_api%7EDAS%7Ekey-LOC_doc%7EUND%7Eab-OR_ser-PAR1_2102029c17568993690712578dba5c-V_4-PAR3_o-RE_new5-P0_0-P1_0&spm=a2c4g.11186623.help-search.i20

Note: qwen-max/qwen-vl-max models are called in the link, new users will have free quotas;
##### 1.1.2 E2B Activation
    Visit the E2B website to register and obtain, then configure to E2B_API_KEY
    https://e2b.dev

##### 1.1.3 Environment Variable Configuration Example

```bash
# Create api-key on the large model service platform DashScope
DASHSCOPE_API_KEY=
# E2B API Key
E2B_API_KEY=
```


You can refer to the global configuration below, or create a new `.env` file in the root directory and paste the above configuration into it, the startup script has logic to read it:

```bash
# macOS/Linux configuration method
nano ~/.zshrc    # If you are using zsh (default in macOS Catalina and later)
# Or
nano ~/.bash_profile  # If you are using bash

# Add environment variables for example
# Cloud computer configuration
export DASHSCOPE_API_KEY="your_api_key_here"
export ECD_DESKTOP_ID="your_desktop_id"
# ... other configurations

# After saving, run
source ~/.zshrc
```


#### 1.4 Local Demo Startup

##### 1.4.1 Enter Directory
```bash
cd demos/computer_use
```


##### 1.4.2 Install Dependencies
```bash
# Execute in the root directory of demos/computer_use to install module dependencies
pip install .
```


##### 1.4.3 Script Authorization and Startup

```bash
cd base_version/computer_use_server
# Grant execution permissions
chmod +x start_base.sh

# Start
./start_base.sh
```


If the E2B framework key is used locally for the first time, and the frontend cannot be started directly by executing [start.sh](./start_base.sh), you can execute separately:

```bash
streamlit run frontend_base.py
```
