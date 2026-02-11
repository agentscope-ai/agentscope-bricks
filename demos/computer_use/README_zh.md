# Computer Use Agent 🤖

## 第一章：概述

Computer Use Agent 是一个基于人工智能的桌面自动化系统，能够通过自然语言指令来控制计算机执行各种任务。该系统结合了计算机视觉、自然语言处理和桌面自动化技术，让用户可以用简单的中文描述来完成复杂的桌面操作。

## 第二章：agentdev 安装

```bash
# 最外层根目录下 agentdev/
pip install .
```

## 第三章：基础使用

在代码目录下base_version 代码包中
- 前端 frontend_base.py
- 后端 backend_base.py
具体参考：[README_zh.md](./base_version/computer_use_server/README_zh.md)

## 第四章: 进阶使用

在代码目录下advanced_version代码包中
- 前端
  - 基础gui版本 computer-use-server/static目录下
  - 高级版本 在代码目录下adk-computer-use代码包中
    - 具体参考：[README_zh.md](./advanced_version/adk-computer-use/README.md)
- 后端 backend.py
具体参考：[README_zh.md](./advanced_version/computer_use_server/README_zh.md)