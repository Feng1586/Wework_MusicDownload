#!/bin/bash

# 音乐下载机器人启动脚本

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
echo "Version: 1.0.3"
echo "启动 FastAPI 服务..."
echo "服务地址: http://0.0.0.0:8000"
echo "回调地址: http://<your-server-ip>:8000/wechat/callback"
echo ""
echo "配置企业微信回调时请使用以上地址"
echo "========================================"

# 启动 Python 服务
exec python main.py