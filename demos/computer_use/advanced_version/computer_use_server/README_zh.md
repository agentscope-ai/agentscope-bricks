# Computer Use Agent 进阶🤖

## 第一章：概述

Computer Use Agent 是一个基于人工智能的桌面自动化系统，能够通过自然语言指令来控制计算机执行各种任务。该系统结合了计算机视觉、自然语言处理和桌面自动化技术，让用户可以用简单的中文描述来完成复杂的桌面操作。

### 🌟 主要特性

- **智能视觉理解**：使用 Qwen 视觉模型理解屏幕内容，精确定位 UI 元素
- **智能推理分析**：使用Gui Agent 推理分析，根据截图，用户query推理，返回下一步动作达到操作目标。
- **自然语言交互**：支持中文自然语言指令，无需编程知识
- **多种操作支持**：
  - 鼠标操作（单击、双击、右击）
  - 键盘输入（文本输入、快捷键）
  - 系统命令执行
  - 屏幕截图和分析
  - 安卓手机操作
- **实时监控**：提供完整的操作日志和实时界面反馈
- **沙盒环境**：基于无影云电脑，无影云手机桌面沙盒，安全隔离执行环境，支持人工干预操作

### 🏗️ 系统架构

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   前端界面      │◄──►│   后端 API      │◄──►│   AI 智能体     │
│  (HTML+JS  )    │    │   (FastAPI)     │    │ (SandboxAgent)  │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                                        │
                                                        ▼
                                              ┌─────────────────┐
                                              │ E2B 沙盒，无影    │
                                              │ (Desktop Env)   │
                                              └─────────────────┘
```

### 🔧 技术栈

- **前端**：HTML + CSS + JavaScript
- **后端**：FastAPI - 高性能异步 API 服务
- **Agent服务**：
  - Mobile Agent
  - PC Agent
- **AI 模型**：
  - Qwen-VL-Max：视觉理解和 GUI 定位
  - Qwen-Max：任务规划和决策
- **自动化**：无影云电脑，云手机云端画面可交互
- **图像处理**：Pillow - 屏幕截图和图像标注
- **云电脑**：无影云电脑 OpenAPI 执行命令、截图等

## 第二章：进阶使用

### Qwen-Max + Gui-Agent + 无影云电脑（windows）/云手机（安卓）接入使用
注意：
- 使用无影云电脑，或者云手机仅购买下文对应资源
- 此版本带有变更云电脑镜像，重置云手机实例镜像的功能，来保证清空用户信息使用痕迹，使用该功能需要几个条件
  - 购买的云电脑安装好下文中python环境依赖，云手机安装好ADBKeyboard.apk后，基于此创建一个镜像作为基础镜像
  - 云电脑可以通过环境变量配置ECD_IMAGE_ID 镜像id，结合代码中的变更镜像逻辑来实现
  - 云手机需要用户自己选创建好的镜像作为镜像，然后程序中走的是重置镜像的逻辑。
  - 也可以关闭重置的逻辑，这样就无需设置镜像了。通过环境变量开关EQUIP_RESET=0关闭，1开启

#### 1. 本地服务启动准备
需要提前安装好python ,推荐3.10
##### 1.1 环境变量配置

##### 1.1.1 灵积百炼平台大模型API-KEY 开通
    介绍文档：
    https://help.aliyun.com/zh/model-studio/get-api-key?scm=20140722.S_help%40%40%E6%96%87%E6%A1%A3%40%402712195._.ID_help%40%40%E6%96%87%E6%A1%A3%40%402712195-RL_api%7EDAS%7Ekey-LOC_doc%7EUND%7Eab-OR_ser-PAR1_2102029c17568993690712578dba5c-V_4-PAR3_o-RE_new5-P0_0-P1_0&spm=a2c4g.11186623.help-search.i20

备注：qwen-max/qwen-vl-max模型在链路中调用，新用户都会有免费额度；

##### 1.1.2 阿里云账号ak ,sk 获取
    介绍文档：
    https://help.aliyun.com/document_detail/53045.html?spm=5176.21213303.aillm.3.7df92f3d4XzQHZ&scm=20140722.S_%E9%98%BF%E9%87%8C%E4%BA%91sk._.RL_%E9%98%BF%E9%87%8C%E4%BA%91sk-LOC_aillm-OR_chat-V_3-RC_llm

##### 1.1.3 oss开通
    介绍文档：
    https://help.aliyun.com/zh/oss/?spm=5176.29463013.J_AHgvE-XDhTWrtotIBlDQQ.8.68b834deqSKlrh

备注：购买完后将账号凭证信息配置到下面环境变量中，也就是EDS_OSS_ 的配置 EDS_OSS_ACCESS_KEY相关的信息就是购买OSS的阿里云账号的ak,sk

##### 1.1.4 无影云电脑开通
  购买云电脑，建议企业版（个人版需要跟无影要一下EndUserId，用于配置环境变量ECD_USERNAME）
目前仅支持windos

      无影个人版文档：
      https://help.aliyun.com/zh/edsp?spm=a2c4g.11174283.d_help_search.i2
      无影企业版文档：
      https://help.aliyun.com/zh/wuying-workspace/product-overview/?spm=a2c4g.11186623.help-menu-68242.d_0.518d5bd7bpQxLq
购买完后将云电脑需要的信息配置到下面环境变量中，也就是ECD_ 的配置
  ALIBABA_CLOUD_ACCESS_KEY相关的信息就是购买云电脑的阿里云账号的ak,sk

##### 1.1.5 无影云手机开通
目前仅支持安卓系统

      控制台：
      https://wya.wuying.aliyun.com/instanceLayouts
      帮助文档：
      https://help.aliyun.com/zh/ecp/?spm=a2c4g.11186623.0.0.62dfe33avAMTwU
  购买完后将云电脑需要的信息配置到下面环境变量中，也就是EDS_ 的配置
  ALIBABA_CLOUD_ACCESS_KEY相关的信息就是购买云手机的阿里云账号的ak,sk

##### 1.1.6 REDIS开通
也可以本地安装redis，或者阿里云redis,推荐阿里云购买

      控制台：
      https://kvstore.console.aliyun.com/Redis/dashboard/cn-hangzhou
      帮助文档：
      https://help.aliyun.com/zh/redis/?spm=5176.29637306.J_AHgvE-XDhTWrtotIBlDQQ.10.627f55b1zAYoBP
  购买完后将云电脑需要的信息配置到下面环境变量中，也就是EDS_ 的配置
  ALIBABA_CLOUD_ACCESS_KEY相关的信息就是购买云手机的阿里云账号的ak,sk


环境变量配置示例

```bash
# 在大模型服务平台百炼,创建api-key
DASHSCOPE_API_KEY=

# 云电脑配置
# ,隔开，设备实例列表
DESKTOP_IDS=
# 企业版可以自己控制台看，个人版需要找无影那边要一下
ECD_USERNAME=
ECD_APP_STREAM_REGION_ID=cn-shanghai
ECD_ALIBABA_CLOUD_REGION_ID=cn-hangzhou
ECD_ALIBABA_CLOUD_ENDPOINT=ecd.cn-hangzhou.aliyuncs.com
ECD_ALIBABA_CLOUD_ACCESS_KEY_ID=
ECD_ALIBABA_CLOUD_ACCESS_KEY_SECRET=
ECD_IMAGE_ID=

# 云手机配置
# ,隔开，设备实例列表
PHONE_INSTANCE_IDS=
EDS_ALIBABA_CLOUD_ENDPOINT=eds-aic.cn-shanghai.aliyuncs.com
EDS_ALIBABA_CLOUD_ACCESS_KEY_ID=
EDS_ALIBABA_CLOUD_ACCESS_KEY_SECRET=

# OSS 配置（根据自己的配置来）
EDS_OSS_ACCESS_KEY_ID=
EDS_OSS_ACCESS_KEY_SECRET=
EDS_OSS_BUCKET_NAME=dashscope-cn-beijing
EDS_OSS_ENDPOINT=http://oss-cn-beijing.aliyuncs.com
EDS_OSS_PATH=bailiansdk-agent-wy/screenshot/

# 激活设备时，是否启动重置 1是 0否
EQUIP_RESET=1
# 人工干预等待时间秒
HUMAN_WAIT_TIME=60

REDIS_HOST=
REDIS_PASSWORD=
REDIS_USERNAME=

```

可以参考下面全局配置，也可以在根目录新建一个 `.env` 文件，将上面的配置粘贴进去，启动脚本中有读取的逻辑：

```bash
# macOS/Linux 配置方法
nano ~/.zshrc    # 如果你用的是 zsh（macOS Catalina 及以后默认）
# 或者
nano ~/.bash_profile  # 如果你用的是 bash

# 添加环境变量例如
# 云电脑配置
export DASHSCOPE_API_KEY=
export ECD_DESKTOP_ID=
# ... 其他配置

# 保存后运行
source ~/.zshrc
```
#### 💻 1.2 云电脑环境准备

如果云电脑已经装好环境，这步不需要配置，但是依赖需要看下是否安装。电脑分辨率1920，1080效果最佳

##### 1.2.1 云电脑 Python 环境安装

以下所有命令都是在云电脑上的 PowerShell 中执行,可以通过下载无影客户端登录到电脑上执行：

```powershell
# 设置下载路径和版本
$version = "3.10.11"
$installerName = "python-$version-amd64.exe"
$downloadUrl = "https://mirrors.aliyun.com/python-release/windows/$installerName"
$pythonInstaller = "$env:TEMP\$installerName"

# 默认安装路径（Python 3.10 安装到 Program Files）
$installDir = "C:\Program Files\Python310"
$scriptsDir = "$installDir\Scripts"

# 下载 Python 安装包（使用阿里云镜像）
Write-Host "正在从阿里云下载 $installerName ..." -ForegroundColor Green
Invoke-WebRequest -Uri $downloadUrl -OutFile $pythonInstaller

# 静默安装 Python（所有用户 + 尝试添加 PATH）
Write-Host "正在安装 Python $version ..." -ForegroundColor Green
Start-Process -Wait -FilePath $pythonInstaller -ArgumentList "/quiet InstallAllUsers=1 PrependPath=0"  # 我们自己加 PATH，所以关闭内置的

# 删除安装包
Remove-Item -Force $pythonInstaller

# ========== 主动添加 Python 到系统 PATH ==========
Write-Host "正在将 Python 添加到系统环境变量 PATH ..." -ForegroundColor Green

# 获取当前系统 PATH（Machine 级别）
$currentPath = [Environment]::GetEnvironmentVariable("Path", "Machine") -split ";"

# 要添加的路径
$pathsToAdd = @($installDir, $scriptsDir)

# 检查并添加
$updated = $false
foreach ($path in $pathsToAdd) {
    if (-not $currentPath.Contains($path) -and (Test-Path $path)) {
        $currentPath += $path
        $updated = $true
        Write-Host "已添加: $path" -ForegroundColor Cyan
    }
}

# 写回系统 PATH
if ($updated) {
    $newPath = $currentPath -join ";"
    [Environment]::SetEnvironmentVariable("Path", $newPath, "Machine")
    Write-Host "系统 PATH 已更新。" -ForegroundColor Green
} else {
    Write-Host "Python 路径已存在于系统 PATH 中。" -ForegroundColor Yellow
}

# ========== 更新当前 PowerShell 会话的 PATH ==========
# 否则当前终端还不能使用 python 命令
$env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [Environment]::GetEnvironmentVariable("Path", "User")

# ========== 检查是否安装成功 ==========
Write-Host "`n检查安装结果：" -ForegroundColor Green
try {
    python --version
} catch {
    Write-Host "python 命令不可用，请重启终端。" -ForegroundColor Red
}

try {
    pip --version
} catch {
    Write-Host "pip 命令不可用，请重启终端。" -ForegroundColor Red
}

# 安装依赖包
python -m pip install pyautogui -i https://mirrors.aliyun.com/pypi/simple/
python -m pip install requests -i https://mirrors.aliyun.com/pypi/simple/
python -m pip install pyperclip -i https://mirrors.aliyun.com/pypi/simple/
python -m pip install pynput -i https://mirrors.aliyun.com/pypi/simple/
python -m pip install aiohttp -i https://mirrors.aliyun.com/pypi/simple/
python -m pip install asyncio -i https://mirrors.aliyun.com/pypi/simple/

```
#### 📱 1.3 云手机环境准备

由于一些app对剪贴板有开启限制，导致文字输入指令无法生效（通过剪贴板实现），所以手机环境需要提前安装好 `ADBKeyboard.apk`。


#### 1.4 本地 Demo 启动

##### 1.4.1 进入目录
```bash
cd demos/computer_use
```

##### 1.4.2 安装依赖
```bash
# 在 demos/computer_use 根目录下执行 安装模块依赖
pip install .
```

##### 1.4.3 启动脚本授权和启动

**注意：云电脑、云手机要保证启动运行中，可以在无影控制台，或者客户端设置。

```bash
cd advanced_version/computer_use_server
# 赋予执行权限
chmod +x start.sh

# 启动
./start.sh
```


#### 1.4.4 使用备注

##### 🖥️ 选择云电脑配置

**注意：** 该 demo 会自动启动唤醒云电脑，为了避免长时间收费，使用后记得关闭窗口，并且云电脑记得设置自动休眠，以免长时间运行中导致费用问题。

##### 📱 选择手机配置

**注意：** 该 demo 使用需要云手机在唤醒状态，为了避免长时间收费，使用后记得关闭窗口，并且记得设置自动休眠，以免长时间运行中导致费用问题。