#!/bin/bash
set -e

echo "=== Grok2API 配置验证 ==="
echo ""

# 颜色定义
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

check_pass() {
    echo -e "${GREEN}✓${NC} $1"
}

check_fail() {
    echo -e "${RED}✗${NC} $1"
}

check_warn() {
    echo -e "${YELLOW}⚠${NC} $1"
}

# 1. 检查必需文件
echo "1. 检查必需文件..."
if [ -f ".env" ]; then
    check_pass ".env 文件存在"
else
    check_fail ".env 文件不存在"
    echo "   运行: cp .env.example .env"
    exit 1
fi

if [ -f "docker-compose.full.yml" ]; then
    check_pass "docker-compose.full.yml 存在"
else
    check_fail "docker-compose.full.yml 不存在"
    exit 1
fi

# 2. 检查环境变量
echo ""
echo "2. 检查环境变量..."
source .env

if [ "$REDIS_PASSWORD" = "changeme" ] || [ -z "$REDIS_PASSWORD" ]; then
    check_warn "REDIS_PASSWORD 使用默认值，生产环境请修改"
else
    check_pass "REDIS_PASSWORD 已设置"
fi

if [ "$MYSQL_PASSWORD" = "changeme" ] || [ -z "$MYSQL_PASSWORD" ]; then
    check_warn "MYSQL_PASSWORD 使用默认值"
else
    check_pass "MYSQL_PASSWORD 已设置"
fi

if [ "$POSTGRES_PASSWORD" = "changeme" ] || [ -z "$POSTGRES_PASSWORD" ]; then
    check_warn "POSTGRES_PASSWORD 使用默认值"
else
    check_pass "POSTGRES_PASSWORD 已设置"
fi

# 3. 检查 Docker
echo ""
echo "3. 检查 Docker..."
if command -v docker &> /dev/null; then
    check_pass "Docker 已安装"
    docker --version
else
    check_fail "Docker 未安装"
    exit 1
fi

if docker compose version &> /dev/null; then
    check_pass "Docker Compose 已安装"
    docker compose version
else
    check_fail "Docker Compose 未安装"
    exit 1
fi

# 4. 检查端口占用
echo ""
echo "4. 检查端口占用..."
if lsof -Pi :8000 -sTCP:LISTEN -t >/dev/null 2>&1 || netstat -an 2>/dev/null | grep -q ":8000.*LISTEN"; then
    check_warn "端口 8000 已被占用"
    echo "   运行: lsof -i :8000 查看占用进程"
else
    check_pass "端口 8000 可用"
fi

if lsof -Pi :6379 -sTCP:LISTEN -t >/dev/null 2>&1 || netstat -an 2>/dev/null | grep -q ":6379.*LISTEN"; then
    check_warn "端口 6379 (Redis) 已被占用"
else
    check_pass "端口 6379 可用"
fi

# 5. 检查 docker-compose 配置
echo ""
echo "5. 验证 docker-compose 配置..."
if docker compose -f docker-compose.full.yml config > /dev/null 2>&1; then
    check_pass "docker-compose.full.yml 配置有效"
else
    check_fail "docker-compose.full.yml 配置无效"
    exit 1
fi

# 6. 检查 GitHub Actions 状态
echo ""
echo "6. GitHub Actions 状态..."
echo "   访问: https://github.com/CPU-JIA/grok2api/actions"
echo "   检查 CI 工作流是否成功"

# 7. 检查 GHCR 镜像
echo ""
echo "7. 检查 Docker 镜像..."
if docker pull ghcr.io/cpu-jia/grok2api:latest 2>/dev/null; then
    check_pass "Docker 镜像可用: ghcr.io/cpu-jia/grok2api:latest"
else
    check_warn "Docker 镜像尚未推送或无法访问"
    echo "   等待 GitHub Actions CI 工作流完成"
fi

echo ""
echo "=== 验证完成 ==="
echo ""
echo "下一步操作:"
echo "1. 如果所有检查通过，运行: ./test-docker.sh"
echo "2. 或手动启动: docker compose -f docker-compose.full.yml --env-file .env --profile redis up -d"
echo "3. 访问管理后台: http://localhost:8000/admin (密码: grok2api)"
