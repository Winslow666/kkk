#!/bin/bash

# 设置端口
PORT=8501

# 检查Python环境
echo "检查Python环境..."
python --version || { echo "未找到Python环境"; exit 1; }

# 检查pip是否可用
echo "检查pip..."
pip --version || { echo "未找到pip"; exit 1; }

# 检查并安装依赖
echo "检查依赖..."
if ! command -v streamlit &> /dev/null; then
    echo "正在安装必要的依赖..."
    pip install -r requirements.txt || { echo "依赖安装失败"; exit 1; }
fi

# 检查网络端口
echo "检查端口 ${PORT} 是否可用..."
if lsof -i:${PORT} > /dev/null; then
    echo "警告: 端口 ${PORT} 已被占用"
    echo "正在尝试关闭已有的Streamlit进程..."
    pkill -f "streamlit run"
    sleep 2
fi

# 清理终端
clear

echo "================================"
echo "🌟 启动旅行规划助手..."
echo "================================"

# 检查应用文件是否存在
if [ ! -f "streamlit_app.py" ]; then
    echo "错误: 找不到 streamlit_app.py"
    exit 1
fi

echo "
应用将在以下地址运行：
🔗 本地访问: http://localhost:${PORT}
🌐 网络访问: http://127.0.0.1:${PORT}
"
echo "正在启动服务..."
echo "--------------------------------"

# 设置Streamlit配置
export STREAMLIT_SERVER_PORT=$PORT
export STREAMLIT_SERVER_ADDRESS=0.0.0.0
export STREAMLIT_SERVER_HEADLESS=true

# 尝试打开浏览器（根据操作系统）
(
    sleep 5  # 给服务更多启动时间
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        open "http://localhost:${PORT}"
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        # Linux
        xdg-open "http://localhost:${PORT}"
    elif [[ "$OSTYPE" == "msys" || "$OSTYPE" == "win32" ]]; then
        # Windows
        start "http://localhost:${PORT}"
    fi
) &

# 运行Streamlit应用（添加调试信息）
streamlit run streamlit_app.py --server.port $PORT --server.address 0.0.0.0 --server.headless true --logger.level info

# 如果streamlit退出，检查是否有错误
if [ $? -ne 0 ]; then
    echo "错误: Streamlit应用启动失败"
    echo "请检查错误信息并重试"
    exit 1
fi 