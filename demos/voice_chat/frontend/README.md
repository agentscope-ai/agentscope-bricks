# 实时语音交互前端应用

这是一个基于React的实时语音交互Web前端应用，配合WebSocket后端服务使用。

## 功能特性

- 🎤 实时语音采集（支持回声消除）
- 💬 流式文本对话显示
- 🔊 实时语音播放
- ⚙️ 可配置的ASR/TTS厂商
- 📝 完整的对话历史记录
- 🎨 简洁现代化的用户界面

## 技术栈

- **前端框架**: React 18 + TypeScript
- **UI组件库**: Ant Design 5.x
- **音频处理**: Recorder.js + Web Audio API
- **WebSocket通信**: 原生WebSocket API
- **构建工具**: Create React App

## 项目结构

```
src/
├── components/          # React组件
│   ├── ConfigPanel.tsx # 配置面板
│   ├── ChatArea.tsx    # 对话区域
│   └── ChatHistory.tsx # 对话历史
├── types/              # TypeScript类型定义
│   └── index.ts
├── utils/              # 工具类
│   ├── audioUtils.ts   # 音频处理
│   └── websocketUtils.ts # WebSocket管理
├── App.tsx            # 主应用组件
└── index.tsx          # 应用入口
```

> **注意**: 开发调试组件（TestPanel、AudioTest）已移除，保持UI简洁

## 快速开始

### 1. 安装依赖

```bash
npm install
```

### 2. 启动开发服务器

```bash
npm start
```

应用将在 http://localhost:3000 启动。

### 3. 构建生产版本

```bash
npm run build
```

## 使用说明

### 配置会话参数

在左侧配置面板中设置：
- **ASR厂商**: 语音识别服务提供商
- **TTS厂商**: 语音合成服务提供商

### 开始对话

1. 点击中间的麦克风按钮开始会话
2. 允许浏览器麦克风权限
3. 开始说话，系统会实时识别并显示
4. AI会流式回复文本和语音
5. 再次点击麦克风按钮结束会话

### 查看对话历史

右侧面板会显示完整的对话记录，包括：
- 时间戳
- 说话者标识（User/Assistant）
- 对话内容

## 开发调试

### 开发模式

```bash
npm start
```

### 代码检查

```bash
npm test
```

### 构建分析

```bash
npm run build
```

## 后端服务要求

确保后端FastAPI服务运行在 `http://127.0.0.1:8000`，并提供以下WebSocket端点：

- **WebSocket URL**: `ws://127.0.0.1:8000/api`
- **消息格式**: JSON格式的文本消息和二进制PCM音频数据

### 支持的消息类型

#### 客户端发送
- `SessionStart`: 开启会话
- `SessionStop`: 关闭会话
- 二进制PCM音频数据

#### 服务端响应
- `SessionStarted`: 会话已开启
- `SessionStopped`: 会话已关闭
- `AudioTranscript`: 语音识别结果
- `ResponseText`: 文本回复
- `ResponseAudioStarted`: 语音回复开始
- `ResponseAudioEnded`: 语音回复结束

## 音频配置

- **采样率**: 16000Hz
- **位深度**: 16bit
- **声道**: 单声道
- **回声消除**: 启用
- **噪声抑制**: 启用
- **自动增益控制**: 启用

## 浏览器兼容性

- Chrome 66+
- Firefox 60+
- Safari 11.1+
- Edge 79+

## 故障排除

### 麦克风权限问题
确保浏览器允许麦克风访问权限。

### WebSocket连接失败
检查后端服务是否正常运行在指定端口。

### 音频播放问题
确保系统音频设备正常工作。
