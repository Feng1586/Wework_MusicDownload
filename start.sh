#!/bin/bash

# 音乐下载机器人启动脚本

# 版本号唯一来源在 utils/version.py，这里不再各写一份
VERSION="$(python -c "from utils.version import __version__; print(__version__)" 2>/dev/null || echo unknown)"
PORT="${PORT:-8000}"
HOST="${HOST:-0.0.0.0}"

echo "========================================"
echo "     MusicDL 企业微信音乐下载机器人"
echo "========================================"

# 显示配置信息（隐藏敏感信息的部分）
echo "企业ID: ${S_CORP_ID:-未设置}"
echo "应用ID: ${AGENT_ID:-未设置}"
echo "代理地址: ${WECHAT_PROXY:-未设置}"

# 创建下载目录
mkdir -p /app/downloads

# 等待数据库/依赖项（如果需要）
# echo "等待依赖项..."
# sleep 5
echo "Version: ${VERSION}"
echo "启动 FastAPI 服务..."
echo "服务地址: http://${HOST}:${PORT}"
echo "回调地址: http://<your-server-ip>:${PORT}/wechat/callback"
echo ""
echo "配置企业微信回调时请使用以上地址"
echo "========================================"

# 启动 Python 服务
exec python main.py
