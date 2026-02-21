"""
分布式缓存层

基于 Redis 的分布式缓存实现，支持：
- 多级缓存（本地 + Redis）
- 缓存预热
- 缓存失效
- 缓存统计

使用 JSON 序列化以确保安全性。
"""

import asyncio
import time
import json
from typing import Any, Optional, Callable, TypeVar
from functools import wraps

from app.core.logger import logger
from app.core.config import get_config

T = TypeVar("T")


class DistributedCache:
    """分布式缓存管理器（使用 JSON 序列化）"""

    def __init__(
        self,
        redis_client: Optional[Any] = None,
        default_ttl: int = 3600,
        key_prefix: str = "grok2api:",
        enable_local_cache: bool = True,
        local_cache_size: int = 1000,
    ):
        """
        初始化分布式缓存

        Args:
            redis_client: Redis 客户端实例
            default_ttl: 默认 TTL（秒）
            key_prefix: 键前缀
            enable_local_cache: 是否启用本地缓存（L1）
            local_cache_size: 本地缓存大小
        """
        self.redis = redis_client
        self.default_ttl = default_ttl
        self.key_prefix = key_prefix
        self.enable_local_cache = enable_local_cache

        # L1 本地缓存（进程内）
        self._local_cache: dict[str, tuple[Any, float]] = {}
        self._local_cache_size = local_cache_size
        self._local_access_order: list[str] = []

        # 统计信息
        self._stats = {
            "l1_hits": 0,
            "l1_misses": 0,
            "l2_hits": 0,
            "l2_misses": 0,
            "sets": 0,
            "deletes": 0,
        }

    def _make_key(self, key: str) -> str:
        """生成完整的缓存键"""
        return f"{self.key_prefix}{key}"

    def _serialize(self, value: Any) -> str:
        """序列化值为 JSON 字符串"""
        try:
            return json.dumps(value, ensure_ascii=False)
        except (TypeError, ValueError) as e:
            logger.warning(f"Failed to serialize value: {e}")
            raise

    def _deserialize(self, data: str) -> Any:
        """反序列化 JSON 字符串为值"""
        try:
            return json.loads(data)
        except (TypeError, ValueError) as e:
            logger.warning(f"Failed to deserialize data: {e}")
            raise

    def _get_from_local(self, key: str) -> tuple[bool, Any]:
        """从本地缓存获取"""
        if not self.enable_local_cache:
            return False, None

        full_key = self._make_key(key)
        if full_key not in self._local_cache:
            self._stats["l1_misses"] += 1
            return False, None

        value, expire_at = self._local_cache[full_key]

        # 检查是否过期
        if expire_at > 0 and time.time() > expire_at:
            del self._local_cache[full_key]
            if full_key in self._local_access_order:
                self._local_access_order.remove(full_key)
            self._stats["l1_misses"] += 1
            return False, None

        # 更新访问顺序
        if full_key in self._local_access_order:
            self._local_access_order.remove(full_key)
        self._local_access_order.append(full_key)

        self._stats["l1_hits"] += 1
        return True, value

    def _set_to_local(self, key: str, value: Any, ttl: int):
        """设置到本地缓存"""
        if not self.enable_local_cache:
            return

        full_key = self._make_key(key)

        # LRU 淘汰
        if len(self._local_cache) >= self._local_cache_size:
            if self._local_access_order:
                lru_key = self._local_access_order.pop(0)
                self._local_cache.pop(lru_key, None)

        expire_at = time.time() + ttl if ttl > 0 else 0
        self._local_cache[full_key] = (value, expire_at)
        self._local_access_order.append(full_key)

    def _delete_from_local(self, key: str):
        """从本地缓存删除"""
        if not self.enable_local_cache:
            return

        full_key = self._make_key(key)
        self._local_cache.pop(full_key, None)
        if full_key in self._local_access_order:
            self._local_access_order.remove(full_key)

    async def get(self, key: str) -> Optional[Any]:
        """
        获取缓存值

        Args:
            key: 缓存键

        Returns:
            缓存值，如果不存在则返回 None
        """
        # L1: 本地缓存
        hit, value = self._get_from_local(key)
        if hit:
            return value

        # L2: Redis 缓存
        if self.redis is None:
            self._stats["l2_misses"] += 1
            return None

        try:
            full_key = self._make_key(key)
            data = await self.redis.get(full_key)

            if data is None:
                self._stats["l2_misses"] += 1
                return None

            # 反序列化
            if isinstance(data, bytes):
                data = data.decode("utf-8")
            value = self._deserialize(data)
            self._stats["l2_hits"] += 1

            # 回填到本地缓存
            ttl = await self.redis.ttl(full_key)
            if ttl > 0:
                self._set_to_local(key, value, ttl)

            return value

        except Exception as e:
            logger.warning(f"Failed to get from Redis cache: {e}")
            self._stats["l2_misses"] += 1
            return None

    async def set(self, key: str, value: Any, ttl: Optional[int] = None):
        """
        设置缓存值

        Args:
            key: 缓存键
            value: 缓存值（必须可 JSON 序列化）
            ttl: TTL（秒），None 使用默认值
        """
        if ttl is None:
            ttl = self.default_ttl

        self._stats["sets"] += 1

        # 设置到本地缓存
        self._set_to_local(key, value, ttl)

        # 设置到 Redis
        if self.redis is None:
            return

        try:
            full_key = self._make_key(key)
            data = self._serialize(value)

            if ttl > 0:
                await self.redis.setex(full_key, ttl, data)
            else:
                await self.redis.set(full_key, data)

        except Exception as e:
            logger.warning(f"Failed to set to Redis cache: {e}")

    async def delete(self, key: str):
        """
        删除缓存值

        Args:
            key: 缓存键
        """
        self._stats["deletes"] += 1

        # 从本地缓存删除
        self._delete_from_local(key)

        # 从 Redis 删除
        if self.redis is None:
            return

        try:
            full_key = self._make_key(key)
            await self.redis.delete(full_key)
        except Exception as e:
            logger.warning(f"Failed to delete from Redis cache: {e}")

    async def exists(self, key: str) -> bool:
        """
        检查缓存键是否存在

        Args:
            key: 缓存键

        Returns:
            是否存在
        """
        # 检查本地缓存
        hit, _ = self._get_from_local(key)
        if hit:
            return True

        # 检查 Redis
        if self.redis is None:
            return False

        try:
            full_key = self._make_key(key)
            return await self.redis.exists(full_key) > 0
        except Exception as e:
            logger.warning(f"Failed to check existence in Redis cache: {e}")
            return False

    async def clear(self, pattern: Optional[str] = None):
        """
        清空缓存

        Args:
            pattern: 键模式（支持通配符），None 表示清空所有
        """
        # 清空本地缓存
        if pattern is None:
            self._local_cache.clear()
            self._local_access_order.clear()
        else:
            # 模式匹配删除
            import fnmatch

            full_pattern = self._make_key(pattern)
            keys_to_delete = [
                k for k in self._local_cache.keys() if fnmatch.fnmatch(k, full_pattern)
            ]
            for k in keys_to_delete:
                self._local_cache.pop(k, None)
                if k in self._local_access_order:
                    self._local_access_order.remove(k)

        # 清空 Redis
        if self.redis is None:
            return

        try:
            if pattern is None:
                # 删除所有带前缀的键
                pattern = "*"

            full_pattern = self._make_key(pattern)
            cursor = 0
            while True:
                cursor, keys = await self.redis.scan(
                    cursor=cursor,
                    match=full_pattern,
                    count=100,
                )
                if keys:
                    await self.redis.delete(*keys)
                if cursor == 0:
                    break

        except Exception as e:
            logger.warning(f"Failed to clear Redis cache: {e}")

    async def get_or_set(
        self,
        key: str,
        factory: Callable[[], T],
        ttl: Optional[int] = None,
    ) -> T:
        """
        获取缓存值，如果不存在则调用工厂函数生成并缓存

        Args:
            key: 缓存键
            factory: 工厂函数（同步或异步）
            ttl: TTL（秒）

        Returns:
            缓存值
        """
        # 尝试获取
        value = await self.get(key)
        if value is not None:
            return value

        # 调用工厂函数
        if asyncio.iscoroutinefunction(factory):
            value = await factory()
        else:
            value = factory()

        # 缓存结果
        await self.set(key, value, ttl)
        return value

    def get_stats(self) -> dict:
        """
        获取缓存统计信息

        Returns:
            统计信息字典
        """
        l1_total = self._stats["l1_hits"] + self._stats["l1_misses"]
        l1_hit_rate = (self._stats["l1_hits"] / l1_total * 100) if l1_total > 0 else 0.0

        l2_total = self._stats["l2_hits"] + self._stats["l2_misses"]
        l2_hit_rate = (self._stats["l2_hits"] / l2_total * 100) if l2_total > 0 else 0.0

        return {
            "l1_size": len(self._local_cache),
            "l1_max_size": self._local_cache_size,
            "l1_hits": self._stats["l1_hits"],
            "l1_misses": self._stats["l1_misses"],
            "l1_hit_rate": f"{l1_hit_rate:.2f}%",
            "l2_hits": self._stats["l2_hits"],
            "l2_misses": self._stats["l2_misses"],
            "l2_hit_rate": f"{l2_hit_rate:.2f}%",
            "sets": self._stats["sets"],
            "deletes": self._stats["deletes"],
        }

    def log_stats(self):
        """记录缓存统计信息到日志"""
        stats = self.get_stats()
        logger.info(
            f"Distributed cache stats: "
            f"L1={stats['l1_size']}/{stats['l1_max_size']} "
            f"(hit_rate={stats['l1_hit_rate']}), "
            f"L2_hit_rate={stats['l2_hit_rate']}, "
            f"sets={stats['sets']}, deletes={stats['deletes']}"
        )


# 全局缓存实例
_distributed_cache: Optional[DistributedCache] = None


async def get_distributed_cache() -> DistributedCache:
    """
    获取全局分布式缓存实例

    Returns:
        DistributedCache 实例
    """
    global _distributed_cache

    if _distributed_cache is None:
        # 尝试连接 Redis
        redis_client = None
        storage_type = get_config("server.storage_type", "local")

        if storage_type == "redis":
            try:
                import redis.asyncio as aioredis

                storage_url = get_config("server.storage_url", "")
                if storage_url:
                    redis_client = await aioredis.from_url(storage_url)
                    logger.info("Distributed cache connected to Redis")
            except Exception as e:
                logger.warning(f"Failed to connect to Redis for cache: {e}")

        _distributed_cache = DistributedCache(
            redis_client=redis_client,
            default_ttl=3600,
            key_prefix="grok2api:cache:",
        )

    return _distributed_cache


def cached(
    key_prefix: str,
    ttl: Optional[int] = None,
    key_builder: Optional[Callable[..., str]] = None,
):
    """
    缓存装饰器

    Args:
        key_prefix: 缓存键前缀
        ttl: TTL（秒）
        key_builder: 自定义键构建函数

    Returns:
        装饰器函数

    Example:
        >>> @cached("user", ttl=300)
        ... async def get_user(user_id: int):
        ...     # 查询用户
        ...     pass
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            cache = await get_distributed_cache()

            # 构建缓存键
            if key_builder:
                cache_key = f"{key_prefix}:{key_builder(*args, **kwargs)}"
            else:
                # 默认使用参数构建键
                key_parts = [str(arg) for arg in args]
                key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
                cache_key = f"{key_prefix}:{':'.join(key_parts)}"

            # 尝试从缓存获取
            value = await cache.get(cache_key)
            if value is not None:
                return value

            # 调用原函数
            if asyncio.iscoroutinefunction(func):
                value = await func(*args, **kwargs)
            else:
                value = func(*args, **kwargs)

            # 缓存结果
            await cache.set(cache_key, value, ttl)
            return value

        return wrapper

    return decorator


__all__ = [
    "DistributedCache",
    "get_distributed_cache",
    "cached",
]
