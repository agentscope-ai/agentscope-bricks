
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

# 设置 PYTHONPATH 以解决模块导入问题
export PYTHONPATH="../../../../:../../../../src:$PYTHONPATH"
echo "🔧 已设置 PYTHONPATH: $PYTHONPATH"

# 启动后端服务
echo "🔧 启动后端服务 (http://localhost:8002)..."
python backend_base.py 2>&1 | sed "s/^/${BLUE}[FastAPI]${NC} /" &
BACKEND_PID=$!

# 等待后端启动
sleep 3

# 启动前端服务
echo "🎨 启动前端界面 (http://localhost:8501)..."
streamlit run frontend_base.py 2>&1 | sed "s/^/${GREEN}[Streamlit]${NC} /" &
FRONTEND_PID=$!

echo "✅ 服务已启动!"
echo "📱 前端界面: http://localhost:8501"
echo "🔧 后端API: http://localhost:8002"
echo ""
echo "按 Ctrl+C 停止所有服务..."

# 捕获 Ctrl+C 并优雅关闭所有子进程
trap 'echo "🛑 正在停止服务..."; kill $(jobs -p) 2>/dev/null; wait $(jobs -p) 2>/dev/null; exit' INT

# 等待所有后台任务完成
wait