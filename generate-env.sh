#!/bin/bash
set -e

echo "=== Grok2API 环境配置生成器 ==="
echo ""

# 检查 .env 是否已存在
if [ -f ".env" ]; then
    echo "⚠️  .env 文件已存在"
    read -p "是否覆盖? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "已取消"
        exit 0
    fi
fi

# 生成随机密码函数
generate_password() {
    openssl rand -base64 32 | tr -d "=+/" | cut -c1-32
}

echo "正在生成随机密码..."

# 生成密码
REDIS_PASSWORD=$(generate_password)
MYSQL_ROOT_PASSWORD=$(generate_password)
MYSQL_PASSWORD=$(generate_password)
POSTGRES_PASSWORD=$(generate_password)
APP_KEY=$(generate_password)
SESSION_SECRET=$(generate_password)

# 创建 .env 文件
cat > .env << EOF
# Grok2API Environment Variables
# Auto-generated on $(date)

# ============================================
# Storage Passwords (for docker-compose.full.yml)
# ============================================

# Redis password
REDIS_PASSWORD=${REDIS_PASSWORD}

# MySQL passwords
MYSQL_ROOT_PASSWORD=${MYSQL_ROOT_PASSWORD}
MYSQL_PASSWORD=${MYSQL_PASSWORD}

# PostgreSQL password
POSTGRES_PASSWORD=${POSTGRES_PASSWORD}

# ============================================
# Application Configuration
# ============================================

# Logging
LOG_LEVEL=INFO
LOG_FILE_ENABLED=true

# Data directory
DATA_DIR=./data

# Server configuration
SERVER_HOST=0.0.0.0
SERVER_PORT=8000
SERVER_WORKERS=1

# Storage backend (local, redis, mysql, pgsql)
SERVER_STORAGE_TYPE=local
# SERVER_STORAGE_URL=

# Examples:
# For Redis:
# SERVER_STORAGE_TYPE=redis
# SERVER_STORAGE_URL=redis://:${REDIS_PASSWORD}@redis:6379/0

# For MySQL:
# SERVER_STORAGE_TYPE=mysql
# SERVER_STORAGE_URL=mysql+aiomysql://grok2api:${MYSQL_PASSWORD}@mysql:3306/grok2api

# For PostgreSQL:
# SERVER_STORAGE_TYPE=pgsql
# SERVER_STORAGE_URL=postgresql+asyncpg://grok2api:${POSTGRES_PASSWORD}@postgres:5432/grok2api

# ============================================
# Security (Optional)
# ============================================
# Override default app_key and session_secret
GROK2API_APP_KEY=${APP_KEY}
GROK2API_SESSION_SECRET=${SESSION_SECRET}
EOF

echo ""
echo "✅ .env 文件已生成"
echo ""
echo "生成的密码（请妥善保管）："
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "REDIS_PASSWORD:        ${REDIS_PASSWORD}"
echo "MYSQL_ROOT_PASSWORD:   ${MYSQL_ROOT_PASSWORD}"
echo "MYSQL_PASSWORD:        ${MYSQL_PASSWORD}"
echo "POSTGRES_PASSWORD:     ${POSTGRES_PASSWORD}"
echo "GROK2API_APP_KEY:      ${APP_KEY}"
echo "GROK2API_SESSION_SECRET: ${SESSION_SECRET}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "下一步："
echo "1. 检查 .env 文件配置"
echo "2. 运行: docker compose -f docker-compose.full.yml --profile redis up -d"
echo "3. 访问: http://localhost:8000/admin"
echo ""
