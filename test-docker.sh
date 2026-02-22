#!/bin/bash
set -e

echo "=== Docker Compose + Redis 测试 ==="

# 1. 清理旧容器
echo "1. 清理旧容器..."
docker compose -f docker-compose.full.yml --profile redis down -v 2>/dev/null || true

# 2. 启动服务
echo "2. 启动 Grok2API + Redis..."
docker compose -f docker-compose.full.yml --env-file .env --profile redis up -d

# 3. 等待服务启动
echo "3. 等待服务启动（30秒）..."
sleep 30

# 4. 检查容器状态
echo "4. 检查容器状态..."
docker compose -f docker-compose.full.yml ps

# 5. 检查健康状态
echo "5. 检查健康状态..."
for i in {1..10}; do
  if curl -f http://localhost:8000/v1/models 2>/dev/null; then
    echo "✅ 健康检查通过"
    break
  fi
  echo "等待服务就绪... ($i/10)"
  sleep 3
done

# 6. 查看日志
echo "6. 最近的日志..."
docker compose -f docker-compose.full.yml logs --tail=20

echo ""
echo "=== 测试完成 ==="
echo "访问: http://localhost:8000/admin"
echo "默认密码: grok2api"
echo ""
echo "停止服务: docker compose -f docker-compose.full.yml --profile redis down"
