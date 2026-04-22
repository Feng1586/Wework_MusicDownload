#!/bin/bash
# 多架构 Docker 镜像构建脚本
# 支持 AMD64 和 ARM64 架构

set -e  # 遇到错误立即退出

echo "========================================"
echo "    MusicDL 多架构 Docker 镜像构建"
echo "========================================"

# 检查 Docker Buildx 是否可用
if ! docker buildx version > /dev/null 2>&1; then
    echo "错误: Docker Buildx 不可用"
    echo "请确保 Docker Desktop 已安装并启用 Buildx"
    exit 1
fi

# 设置变量
IMAGE_NAME="66211900/wecom-musicdl"  # 你的 DockerHub 用户名/镜像名
VERSION="${1}"                       # 版本号，如 v1.2.0
PLATFORMS="linux/amd64,linux/arm64"

# 构建标签列表
TAGS=()
TAGS+=("--tag" "${IMAGE_NAME}:latest")

if [ -n "$VERSION" ]; then
    TAGS+=("--tag" "${IMAGE_NAME}:${VERSION}")
    echo "镜像标签: latest, ${VERSION}"
else
    echo "镜像标签: latest (未指定版本号，仅推送 latest)"
    echo "用法: $0 <版本号>"
    echo "示例: $0 v1.2.0"
fi
echo "目标架构: ${PLATFORMS}"
echo ""

# 创建并启用 Buildx 构建器
echo "1. 设置 Buildx 构建器..."
docker buildx create --name multiarch-builder --use > /dev/null 2>&1 || true
docker buildx use multiarch-builder

# 启动构建器（如果未运行）
if ! docker buildx inspect multiarch-builder | grep -q "Status: running"; then
    echo "  启动构建器..."
    docker buildx inspect --bootstrap
fi

echo ""
echo "2. 构建多架构镜像..."
docker buildx build \
    --platform ${PLATFORMS} \
    "${TAGS[@]}" \
    --push \
    .

echo ""
echo "3. 验证镜像..."
echo "latest 标签:"
docker manifest inspect ${IMAGE_NAME}:latest | grep -A 5 '"architecture" : "amd64"'
echo ""
if [ -n "$VERSION" ]; then
    echo "${VERSION} 标签:"
    docker manifest inspect ${IMAGE_NAME}:${VERSION} | grep -A 5 '"architecture" : "arm64"'
    echo ""
fi

echo ""
echo "========================================"
echo "构建完成!"
echo "镜像已推送到 DockerHub:"
echo "  - ${IMAGE_NAME}:latest"
if [ -n "$VERSION" ]; then
    echo "  - ${IMAGE_NAME}:${VERSION}"
fi
echo "支持的架构: AMD64 (x86_64) 和 ARM64 (Apple Silicon/M1/M2/M3)"
echo "========================================"

# 本地测试（可选）
echo ""
echo "可选本地测试:"
echo "  # 拉取并运行 AMD64 版本"
echo "  docker pull --platform linux/amd64 ${IMAGE_NAME}:latest"
echo "  docker run --rm ${IMAGE_NAME}:latest python --version"
echo ""
echo "  # 拉取并运行 ARM64 版本"
echo "  docker pull --platform linux/arm64 ${IMAGE_NAME}:latest"
echo "  docker run --rm ${IMAGE_NAME}:latest python --version"