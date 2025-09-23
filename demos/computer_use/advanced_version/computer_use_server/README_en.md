# Computer Use Agent Advanced 🤖

## Chapter 1: Overview

Computer Use Agent is an AI-based desktop automation system that can control the computer to perform various tasks through natural language instructions. The system combines computer vision, natural language processing, and desktop automation technologies, allowing users to complete complex desktop operations with simple Chinese descriptions.

### 🌟 Key Features

- **Intelligent Visual Understanding**: Uses Qwen vision model to understand screen content and accurately locate UI elements
- **Intelligent Reasoning Analysis**: Uses Gui Agent for reasoning analysis, inferring from screenshots and user queries to return the next action to achieve the operation goal
- **Natural Language Interaction**: Supports Chinese natural language instructions without programming knowledge
- **Multiple Operation Support**:
  - Mouse operations (click, double-click, right-click)
  - Keyboard input (text input, shortcuts)
  - System command execution
  - Screen capture and analysis
  - Android phone operations
- **Real-time Monitoring**: Provides complete operation logs and real-time interface feedback
- **Sandbox Environment**: Based on Wuying Cloud Computer and Wuying Cloud Phone desktop sandbox, secure isolated execution environment, supports manual intervention operations

### 🏗️ System Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Frontend UI   │◄──►│   Backend API   │◄──►│   AI Agent      │
│  (HTML+JS  )    │    │   (FastAPI)     │    │ (SandboxAgent)  │
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

- **Frontend**: HTML + CSS + JavaScript
- **Backend**: FastAPI - High-performance asynchronous API service
- **Agent Services**:
  - Mobile Agent
  - PC Agent
- **AI Models**:
  - Qwen-VL-Max: Visual understanding and GUI positioning
  - Qwen-Max: Task planning and decision making
- **Automation**: Wuying Cloud Computer, Cloud Phone cloud画面 interactive
- **Image Processing**: Pillow - Screen capture and image annotation
- **Cloud Computer**: Wuying Cloud Computer OpenAPI for executing commands, screenshots, etc.

## Chapter 2: Advanced Usage

### Qwen-Max + Gui-Agent + Wuying Cloud Computer (Windows) / Cloud Phone (Android) Integration Usage
Note:
- Using Wuying Cloud Computer or Cloud Phone only requires purchasing the corresponding resources mentioned below
- This version includes the function to change cloud computer images and reset cloud phone instance images to ensure clearing user information traces. Several conditions are required to use this function:
  - Install the Python environment dependencies mentioned below on the purchased cloud computer, and install ADBKeyboard.apk on the cloud phone, then create an image based on this as the base image
  - Cloud computers can configure the ECD_IMAGE_ID image ID through environment variables, combined with the image change logic in the code
  - Cloud phones need users to select a created image as the image, and the program follows the reset image logic
  - The reset logic can also be disabled, so no image setting is needed. Disable through environment variable switch EQUIP_RESET=0, 1 to enable

#### 1. Local Service Startup Preparation
Python needs to be installed in advance, version 3.10 recommended
##### 1.1 Environment Variable Configuration

##### 1.1.1 DashScope Platform Large Model API-KEY Activation
    Documentation:
    https://help.aliyun.com/zh/model-studio/get-api-key?scm=20140722.S_help%40%40%E6%96%87%E6%A1%A3%40%402712195._.ID_help%40%40%E6%96%87%E6%A1%A3%40%402712195-RL_api%7EDAS%7Ekey-LOC_doc%7EUND%7Eab-OR_ser-PAR1_2102029c17568993690712578dba5c-V_4-PAR3_o-RE_new5-P0_0-P1_0&spm=a2c4g.11186623.help-search.i20

Note: qwen-max/qwen-vl-max models are called in the link, new users will have free quotas;

##### 1.1.2 Alibaba Cloud Account AK, SK Acquisition
    Documentation:
    https://help.aliyun.com/document_detail/53045.html?spm=5176.21213303.aillm.3.7df92f3d4XzQHZ&scm=20140722.S_%E9%98%BF%E9%87%8C%E4%BA%91sk._.RL_%E9%98%BF%E9%87%8C%E4%BA%91sk-LOC_aillm-OR_chat-V_3-RC_llm

##### 1.1.3 OSS Activation
    Documentation:
    https://help.aliyun.com/zh/oss/?spm=5176.29463013.J_AHgvE-XDhTWrtotIBlDQQ.8.68b834deqSKlrh

Note: After purchase, configure the account credential information to the environment variables below, that is, the EDS_OSS_ configuration. The EDS_OSS_ACCESS_KEY related information is the ak, sk of the Alibaba Cloud account that purchased OSS

##### 1.1.4 Wuying Cloud Computer Activation
  Purchase cloud computer, enterprise edition recommended (personal edition needs to request EndUserId from Wuying for configuring environment variable ECD_USERNAME)
Currently only supports Windows

      Wuying Personal Edition Documentation:
      https://help.aliyun.com/zh/edsp?spm=a2c4g.11174283.d_help_search.i2
      Wuying Enterprise Edition Documentation:
      https://help.aliyun.com/zh/wuying-workspace/product-overview/?spm=a2c4g.11186623.help-menu-68242.d_0.518d5bd7bpQxLq
After purchase, configure the cloud computer information needed in the environment variables below, that is, the ECD_ configuration
  The ALIBABA_CLOUD_ACCESS_KEY related information is the ak, sk of the Alibaba Cloud account that purchased the cloud computer

##### 1.1.5 Wuying Cloud Phone Activation
Currently only supports Android system

      Console:
      https://wya.wuying.aliyun.com/instanceLayouts
      Help Documentation:
      https://help.aliyun.com/zh/ecp/?spm=a2c4g.11186623.0.0.62dfe33avAMTwU
  After purchase, configure the cloud computer information needed in the environment variables below, that is, the EDS_ configuration
  The ALIBABA_CLOUD_ACCESS_KEY related information is the ak, sk of the Alibaba Cloud account that purchased the cloud phone

##### 1.1.6 Redis Activation
You can also install redis locally or Alibaba Cloud redis, Alibaba Cloud purchase recommended

      Console:
      https://kvstore.console.aliyun.com/Redis/dashboard/cn-hangzhou
      Help Documentation:
      https://help.aliyun.com/zh/redis/?spm=5176.29637306.J_AHgvE-XDhTWrtotIBlDQQ.10.627f55b1zAYoBP
  After purchase, configure the cloud computer information needed in the environment variables below, that is, the EDS_ configuration
  The ALIBABA_CLOUD_ACCESS_KEY related information is the ak, sk of the Alibaba Cloud account that purchased the cloud phone


Environment Variable Configuration Example

```bash
# Create api-key on the large model service platform DashScope
DASHSCOPE_API_KEY=

# Cloud Computer Configuration
# Separated by commas, device instance list
DESKTOP_IDS=
# Enterprise edition can be viewed on the console, personal edition needs to request from Wuying
ECD_USERNAME=
ECD_APP_STREAM_REGION_ID=cn-shanghai
ECD_ALIBABA_CLOUD_REGION_ID=cn-hangzhou
ECD_ALIBABA_CLOUD_ENDPOINT=ecd.cn-hangzhou.aliyuncs.com
ECD_ALIBABA_CLOUD_ACCESS_KEY_ID=
ECD_ALIBABA_CLOUD_ACCESS_KEY_SECRET=
ECD_IMAGE_ID=

# Cloud Phone Configuration
# Separated by commas, device instance list
PHONE_INSTANCE_IDS=
EDS_ALIBABA_CLOUD_ENDPOINT=eds-aic.cn-shanghai.aliyuncs.com
EDS_ALIBABA_CLOUD_ACCESS_KEY_ID=
EDS_ALIBABA_CLOUD_ACCESS_KEY_SECRET=

# OSS Configuration (configure according to your own settings)
EDS_OSS_ACCESS_KEY_ID=
EDS_OSS_ACCESS_KEY_SECRET=
EDS_OSS_BUCKET_NAME=dashscope-cn-beijing
EDS_OSS_ENDPOINT=http://oss-cn-beijing.aliyuncs.com
EDS_OSS_PATH=bailiansdk-agent-wy/screenshot/

# Whether to start reset when activating device 1 yes 0 no
EQUIP_RESET=1
# Manual intervention wait time in seconds
HUMAN_WAIT_TIME=60

REDIS_HOST=
REDIS_PASSWORD=
REDIS_USERNAME=

```


You can refer to the global configuration below, or create a new `.env` file in the root directory and paste the above configuration into it. The startup script has logic to read it:

```bash
# macOS/Linux Configuration Method
nano ~/.zshrc    # If you are using zsh (default in macOS Catalina and later)
# Or
nano ~/.bash_profile  # If you are using bash

# Add environment variables for example
# Cloud computer configuration
export DASHSCOPE_API_KEY=""
export ECD_DESKTOP_ID="your_desktop_id"
# ... other configurations

# Save and run
source ~/.zshrc
```

#### 💻 1.2 Cloud Computer Environment Preparation

If the cloud computer already has the environment installed, this step is not required, but check if the dependencies are installed. Computer resolution of 1920x1080 works best

##### 1.2.1 Cloud Computer Python Environment Installation

All the following commands are executed in PowerShell on the cloud computer, which can be accessed by downloading the Wuying client and logging into the computer:

```powershell
# Set download path and version
$version = "3.10.11"
$installerName = "python-$version-amd64.exe"
$downloadUrl = "https://mirrors.aliyun.com/python-release/windows/$installerName"
$pythonInstaller = "$env:TEMP\$installerName"

# Default installation path (Python 3.10 installed to Program Files)
$installDir = "C:\Program Files\Python310"
$scriptsDir = "$installDir\Scripts"

# Download Python installer (using Alibaba Cloud mirror)
Write-Host "Downloading $installerName from Alibaba Cloud..." -ForegroundColor Green
Invoke-WebRequest -Uri $downloadUrl -OutFile $pythonInstaller

# Silent install Python (all users + try to add PATH)
Write-Host "Installing Python $version..." -ForegroundColor Green
Start-Process -Wait -FilePath $pythonInstaller -ArgumentList "/quiet InstallAllUsers=1 PrependPath=0"  # We add PATH ourselves, so disable built-in

# Delete installer
Remove-Item -Force $pythonInstaller

# ========== Manually add Python to system PATH ==========
Write-Host "Adding Python to system environment variable PATH..." -ForegroundColor Green

# Get current system PATH (Machine level)
$currentPath = [Environment]::GetEnvironmentVariable("Path", "Machine") -split ";"

# Paths to add
$pathsToAdd = @($installDir, $scriptsDir)

# Check and add
$updated = $false
foreach ($path in $pathsToAdd) {
    if (-not $currentPath.Contains($path) -and (Test-Path $path)) {
        $currentPath += $path
        $updated = $true
        Write-Host "Added: $path" -ForegroundColor Cyan
    }
}

# Write back system PATH
if ($updated) {
    $newPath = $currentPath -join ";"
    [Environment]::SetEnvironmentVariable("Path", $newPath, "Machine")
    Write-Host "System PATH updated." -ForegroundColor Green
} else {
    Write-Host "Python path already exists in system PATH." -ForegroundColor Yellow
}

# ========== Update current PowerShell session PATH ==========
# Otherwise current terminal cannot use python command
$env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [Environment]::GetEnvironmentVariable("Path", "User")

# ========== Check if installation was successful ==========
Write-Host "`nChecking installation results:" -ForegroundColor Green
try {
    python --version
} catch {
    Write-Host "python command not available, please restart terminal." -ForegroundColor Red
}

try {
    pip --version
} catch {
    Write-Host "pip command not available, please restart terminal." -ForegroundColor Red
}

# Install dependency packages
python -m pip install pyautogui -i https://mirrors.aliyun.com/pypi/simple/
python -m pip install requests -i https://mirrors.aliyun.com/pypi/simple/
python -m pip install pyperclip -i https://mirrors.aliyun.com/pypi/simple/
python -m pip install pynput -i https://mirrors.aliyun.com/pypi/simple/
python -m pip install aiohttp -i https://mirrors.aliyun.com/pypi/simple/
python -m pip install asyncio -i https://mirrors.aliyun.com/pypi/simple/

```

#### 📱 1.3 Cloud Phone Environment Preparation

Due to some apps having clipboard access restrictions, text input commands may not work (implemented through clipboard), so the phone environment needs to have `ADBKeyboard.apk` installed in advance.


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

**Note: Cloud computer and cloud phone must be running. Can be set in Wuying console or client.

```bash
cd advanced_version/computer_use_server
# Grant execution permissions
chmod +x start.sh

# Start
./start.sh
```



#### 1.4.4 Usage Notes

##### 🖥️ Cloud Computer Configuration Selection

**Note:** This demo will automatically start and wake up the cloud computer. To avoid long-term charges, remember to close the window after use, and set the cloud computer to auto-sleep to avoid cost issues from long-term operation.

##### 📱 Phone Configuration Selection

**Note:** This demo requires the cloud phone to be in a wake state. To avoid long-term charges, remember to close the window after use, and set auto-sleep to avoid cost issues from long-term operation.