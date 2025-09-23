# Computer Use Agent 基础版 🤖

## 第一章：概述

Computer Use Agent 是一个基于人工智能的桌面自动化系统，能够通过自然语言指令来控制计算机执行各种任务。该系统结合了计算机视觉、自然语言处理和桌面自动化技术，让用户可以用简单的中文描述来完成复杂的桌面操作。

### 🌟 主要特性

- **智能视觉理解**：使用 Qwen 视觉模型理解屏幕内容，精确定位 UI 元素
- **自然语言交互**：支持中文自然语言指令，无需编程知识
- **多种操作支持**：
  - 鼠标操作（单击、双击、右击）
  - 键盘输入（文本输入、快捷键）
  - 系统命令执行
  - 屏幕截图和分析
- **实时监控**：提供完整的操作日志和实时界面反馈
- **沙盒环境**：基于 E2B sandbox，无影云电脑，无影云手机 桌面沙盒，安全隔离执行环境，，支持人工干预操作

### 🏗️ 系统架构

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   前端界面      │◄──►│   后端 API      │◄──►│   AI 智能体应用     │
│  (Streamlit)    │    │   (FastAPI)     │    │ (GuiAgent)  │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                                        │
                                                        ▼
                                              ┌─────────────────┐
                                              │ E2B 沙盒，无影    │
                                              │ (Desktop Env)   │
                                              └─────────────────┘
```

### 🔧 技术栈

- **前端**：Streamlit - 现代化 Web 界面
- **后端**：FastAPI - 高性能异步 API 服务
- **Agent服务**：
  - Gui Agent
- **AI 模型**：
  - Qwen-VL-Max：视觉理解和 GUI 定位
  - Qwen-Max：任务规划和决策
- **自动化**：E2B Desktop - 安全的桌面沙盒环境
- **图像处理**：Pillow - 屏幕截图和图像标注

## 第二章：基础版本使用

### Qwen-Max + Qwen-VL-MAX + E2B Desktop接入使用
注意：
  - 开通DASHSCOPE_API_KEY
  - 开通E2B
  - E2B 目前仅支持英文query
#### 1. 本地服务启动准备
需要提前安装好python ,推荐3.10
##### 1.1 环境变量配置

##### 1.1.1 灵积百炼平台大模型API-KEY 开通
    介绍文档：
    https://help.aliyun.com/zh/model-studio/get-api-key?scm=20140722.S_help%40%40%E6%96%87%E6%A1%A3%40%402712195._.ID_help%40%40%E6%96%87%E6%A1%A3%40%402712195-RL_api%7EDAS%7Ekey-LOC_doc%7EUND%7Eab-OR_ser-PAR1_2102029c17568993690712578dba5c-V_4-PAR3_o-RE_new5-P0_0-P1_0&spm=a2c4g.11186623.help-search.i20

备注：qwen-max/qwen-vl-max模型在链路中调用，新用户都会有免费额度；
##### 1.1.2 E2B 开通
    访问E2B官网注册并获取，然后配置到E2B_API_KEY
    https://e2b.dev

##### 1.1.3 oss开通
    如果需要使用agent 框架，也就是选择pc-use， 需要OSS配置,直接走qwen-vl 不需要
    介绍文档：
    https://help.aliyun.com/zh/oss/?spm=5176.29463013.J_AHgvE-XDhTWrtotIBlDQQ.8.68b834deqSKlrh

备注：购买完后将账号凭证信息配置到下面环境变量中，也就是EDS_OSS_ 的配置 EDS_OSS_ACCESS_KEY相关的信息就是购买OSS的阿里云账号的ak,sk

##### 1.1.4环境变量配置示例

```bash
# 在大模型服务平台百炼,创建api-key
DASHSCOPE_API_KEY=
# E2B API Key
E2B_API_KEY=
# OSS 配置
EDS_OSS_ACCESS_KEY_ID=
EDS_OSS_ACCESS_KEY_SECRET=
EDS_OSS_BUCKET_NAME=
EDS_OSS_ENDPOINT=
EDS_OSS_PATH=

```

可以参考下面全局配置，也可以在根目录新建一个 `.env` 文件，将上面的配置粘贴进去，启动脚本中有读取的逻辑：

```bash
# macOS/Linux 配置方法
nano ~/.zshrc    # 如果你用的是 zsh（macOS Catalina 及以后默认）
# 或者
nano ~/.bash_profile  # 如果你用的是 bash

# 添加环境变量例如
export DASHSCOPE_API_KEY=""
export ECD_DESKTOP_ID="your_desktop_id"
export EDS_OSS_ACCESS_KEY_ID=
export EDS_OSS_ACCESS_KEY_SECRET=
export EDS_OSS_BUCKET_NAME=
export EDS_OSS_ENDPOINT=
export EDS_OSS_PATH=

# 保存后运行
source ~/.zshrc
```

#### 1.2 本地 Demo 启动

##### 1.2.1 进入目录
```bash
cd demos/computer_use
```

##### 1.2.2 安装依赖
```bash
# 在 demos/computer_use 根目录下执行 安装模块依赖
pip install .
```

##### 1.2.3 启动脚本授权和启动

```bash
cd base_version/computer_use_server
# 赋予执行权限
chmod +x start_base.sh

# 启动
./start_base.sh
```

如果 E2B 框架的 key 第一次在本地使用，并且直接执行 `start.sh` 启动不起来前端，可以单独执行：

```bash
streamlit run frontend_base.py
```
