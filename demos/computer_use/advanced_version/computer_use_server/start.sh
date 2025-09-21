#!/bin/bash

echo "🚀 启动 Computer Use Agent..."

# 加载环境变量
if [ -f ".env" ]; then
    echo "📋 加载环境变量..."
    set -a  # 自动导出所有变量
    source .env
    set +a  # 关闭自动导出
    echo "✅ 环境变量已加载"
else
    echo "⚠️  未找到 .env 文件"
fi

# 定义颜色
BLUE=$(printf '\033[0;34m')
GREEN=$(printf '\033[0;32m')
NC=$(printf '\033[0m')

export PYTHONPATH="../../../..:../../../../src:$PYTHONPATH"
echo "🔧 已设置 PYTHONPATH: $PYTHONPATH"

# 启动后端服务
echo "🔧 启动后端服务..."
python3 backend.py  &

# 等待后端启动
sleep 3

# 启动前端静态资源服务
echo "🎨 启动前端静态资源服务..."
cd static || { echo "❌ 无法进入 static 目录"; exit 1; }
python3 -m http.server 8001 --bind 127.0.0.1 &

# 启动 Nginx 如果本地不需要，可以注释
#echo "🌐 启动 Nginx 服务..."
#sudo nginx

echo "✅ 服务已启动!"
echo "📱 访问地址: http://localhost:8001/index.html"
echo ""

echo "按 Ctrl+C 停止所有服务..."

# 等待用户中断
trap "echo '🛑 正在停止服务...'; sudo nginx -s stop; pkill -P $$; exit" INT
wait
