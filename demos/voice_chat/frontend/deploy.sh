#!/bin/bash

echo "开始构建语音聊天前端应用..."

# 安装依赖
echo "安装依赖..."
npm install

# 构建生产版本
echo "构建生产版本..."
npm run build

# 检查构建是否成功
if [ $? -eq 0 ]; then
    echo "✅ 构建成功！"
    echo "📁 构建文件位于 build/ 目录"
    echo "🌐 可以使用以下命令启动静态服务器："
    echo "   npm install -g serve"
    echo "   serve -s build"
else
    echo "❌ 构建失败！"
    exit 1
fi