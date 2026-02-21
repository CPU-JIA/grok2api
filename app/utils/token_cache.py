"""
Token 选择 LRU 缓存

为热点 Token 提供 LRU 缓存机制，减少 Token 池查询开销。
"""

from functools import lru_cache
from typing import Optional, Set
import time

from app.core.logger import logger
from app.services.token.models import EffortType


class TokenCache:
    """Token 缓存管理器"""

    def __init__(self, max_size: int = 100, ttl_seconds: float = 60.0):
        """
        初始化 Token 缓存

        Args:
            max_size: 缓存最大容量
            ttl_seconds: 缓存 TTL（秒）
        """
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self._cache: dict[tuple, tuple[str, float]] = (
            {}
        )  # (pool_name, effort) -> (token, timestamp)
        self._access_order: list[tuple] = []  # LRU 访问顺序
        self._hits = 0
        self._misses = 0

    def get(
        self, pool_name: str, effort: EffortType, exclude: Optional[Set[str]] = None
    ) -> Optional[str]:
        """
        从缓存获取 Token

        Args:
            pool_name: Token 池名称
            effort: 努力类型
            exclude: 排除的 Token 集合

        Returns:
            Token 字符串，如果未命中则返回 None
        """
        key = (pool_name, effort.value)

        if key not in self._cache:
            self._misses += 1
            return None

        token, timestamp = self._cache[key]

        # 检查 TTL
        if time.monotonic() - timestamp > self.ttl_seconds:
            self._remove(key)
            self._misses += 1
            return None

        # 检查是否在排除列表中
        if exclude and token in exclude:
            self._misses += 1
            return None

        # 更新访问顺序（移到最后）
        if key in self._access_order:
            self._access_order.remove(key)
        self._access_order.append(key)

        self._hits += 1
        return token

    def put(self, pool_name: str, effort: EffortType, token: str):
        """
        将 Token 放入缓存

        Args:
            pool_name: Token 池名称
            effort: 努力类型
            token: Token 字符串
        """
        key = (pool_name, effort.value)
        timestamp = time.monotonic()

        # 如果已存在，更新时间戳
        if key in self._cache:
            self._cache[key] = (token, timestamp)
            if key in self._access_order:
                self._access_order.remove(key)
            self._access_order.append(key)
            return

        # 检查容量，LRU 淘汰
        if len(self._cache) >= self.max_size:
            self._evict_lru()

        self._cache[key] = (token, timestamp)
        self._access_order.append(key)

    def invalidate(self, token: str):
        """
        使指定 Token 的缓存失效

        Args:
            token: Token 字符串
        """
        keys_to_remove = []
        for key, (cached_token, _) in self._cache.items():
            if cached_token == token:
                keys_to_remove.append(key)

        for key in keys_to_remove:
            self._remove(key)

    def invalidate_pool(self, pool_name: str):
        """
        使指定池的所有缓存失效

        Args:
            pool_name: Token 池名称
        """
        keys_to_remove = [key for key in self._cache.keys() if key[0] == pool_name]
        for key in keys_to_remove:
            self._remove(key)

    def clear(self):
        """清空所有缓存"""
        self._cache.clear()
        self._access_order.clear()
        self._hits = 0
        self._misses = 0

    def _remove(self, key: tuple):
        """移除缓存项"""
        if key in self._cache:
            del self._cache[key]
        if key in self._access_order:
            self._access_order.remove(key)

    def _evict_lru(self):
        """淘汰最久未使用的缓存项"""
        if not self._access_order:
            return

        lru_key = self._access_order.pop(0)
        if lru_key in self._cache:
            del self._cache[lru_key]

    def get_stats(self) -> dict:
        """
        获取缓存统计信息

        Returns:
            统计信息字典
        """
        total = self._hits + self._misses
        hit_rate = (self._hits / total * 100) if total > 0 else 0.0

        return {
            "size": len(self._cache),
            "max_size": self.max_size,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": f"{hit_rate:.2f}%",
            "ttl_seconds": self.ttl_seconds,
        }

    def log_stats(self):
        """记录缓存统计信息到日志"""
        stats = self.get_stats()
        logger.info(
            f"Token cache stats: size={stats['size']}/{stats['max_size']}, "
            f"hits={stats['hits']}, misses={stats['misses']}, "
            f"hit_rate={stats['hit_rate']}"
        )


# 全局缓存实例
_token_cache: Optional[TokenCache] = None


def get_token_cache(max_size: int = 100, ttl_seconds: float = 60.0) -> TokenCache:
    """
    获取全局 Token 缓存实例

    Args:
        max_size: 缓存最大容量
        ttl_seconds: 缓存 TTL（秒）

    Returns:
        TokenCache 实例
    """
    global _token_cache
    if _token_cache is None:
        _token_cache = TokenCache(max_size=max_size, ttl_seconds=ttl_seconds)
    return _token_cache


__all__ = [
    "TokenCache",
    "get_token_cache",
]
