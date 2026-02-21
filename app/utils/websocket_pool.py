"""
WebSocket 连接池

为 WebSocket 连接提供连接池复用，减少连接建立开销。
"""

import asyncio
import time
from typing import Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum

from app.core.logger import logger


class ConnectionState(Enum):
    """连接状态"""

    IDLE = "idle"  # 空闲
    ACTIVE = "active"  # 使用中
    CLOSED = "closed"  # 已关闭


@dataclass
class PooledConnection:
    """池化连接"""

    connection: Any  # WebSocket 连接对象
    state: ConnectionState = ConnectionState.IDLE
    created_at: float = 0.0
    last_used_at: float = 0.0
    use_count: int = 0

    def __post_init__(self):
        if self.created_at == 0.0:
            self.created_at = time.monotonic()
        if self.last_used_at == 0.0:
            self.last_used_at = self.created_at


class WebSocketPool:
    """WebSocket 连接池"""

    def __init__(
        self,
        max_size: int = 10,
        max_idle_time: float = 300.0,  # 5 分钟
        max_lifetime: float = 3600.0,  # 1 小时
        health_check_interval: float = 60.0,  # 1 分钟
    ):
        """
        初始化连接池

        Args:
            max_size: 连接池最大容量
            max_idle_time: 最大空闲时间（秒）
            max_lifetime: 连接最大生命周期（秒）
            health_check_interval: 健康检查间隔（秒）
        """
        self.max_size = max_size
        self.max_idle_time = max_idle_time
        self.max_lifetime = max_lifetime
        self.health_check_interval = health_check_interval

        self._pool: Dict[str, PooledConnection] = {}
        self._lock = asyncio.Lock()
        self._health_check_task: Optional[asyncio.Task] = None
        self._closed = False

        # 统计信息
        self._stats = {
            "total_created": 0,
            "total_reused": 0,
            "total_closed": 0,
            "total_health_check_failures": 0,
        }

    async def start(self):
        """启动连接池（启动健康检查任务）"""
        if self._health_check_task is None:
            self._health_check_task = asyncio.create_task(self._health_check_loop())
            logger.info("WebSocket pool health check started")

    async def stop(self):
        """停止连接池"""
        self._closed = True

        # 停止健康检查任务
        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass
            self._health_check_task = None

        # 关闭所有连接
        async with self._lock:
            for key, pooled in list(self._pool.items()):
                await self._close_connection(pooled)
                del self._pool[key]

        logger.info("WebSocket pool stopped")

    async def acquire(
        self,
        key: str,
        factory: callable,
        *args,
        **kwargs,
    ) -> Any:
        """
        获取连接

        Args:
            key: 连接键（用于标识连接，如 URL）
            factory: 连接工厂函数（用于创建新连接）
            *args: 工厂函数参数
            **kwargs: 工厂函数关键字参数

        Returns:
            WebSocket 连接对象
        """
        if self._closed:
            raise RuntimeError("WebSocket pool is closed")

        async with self._lock:
            # 尝试从池中获取空闲连接
            if key in self._pool:
                pooled = self._pool[key]

                # 检查连接是否可用
                if pooled.state == ConnectionState.IDLE:
                    # 检查连接是否过期
                    now = time.monotonic()
                    if now - pooled.created_at > self.max_lifetime:
                        logger.debug(f"Connection expired: {key}")
                        await self._close_connection(pooled)
                        del self._pool[key]
                    elif now - pooled.last_used_at > self.max_idle_time:
                        logger.debug(f"Connection idle timeout: {key}")
                        await self._close_connection(pooled)
                        del self._pool[key]
                    else:
                        # 连接可用，复用
                        pooled.state = ConnectionState.ACTIVE
                        pooled.last_used_at = now
                        pooled.use_count += 1
                        self._stats["total_reused"] += 1
                        logger.debug(
                            f"Reusing connection: {key} (use_count={pooled.use_count})"
                        )
                        return pooled.connection

            # 检查连接池是否已满
            if len(self._pool) >= self.max_size:
                # 尝试清理过期连接
                await self._cleanup_expired()

                # 如果仍然满，抛出异常
                if len(self._pool) >= self.max_size:
                    raise RuntimeError(
                        f"WebSocket pool is full (max_size={self.max_size})"
                    )

            # 创建新连接
            connection = await factory(*args, **kwargs)
            pooled = PooledConnection(
                connection=connection,
                state=ConnectionState.ACTIVE,
            )
            self._pool[key] = pooled
            self._stats["total_created"] += 1
            logger.debug(f"Created new connection: {key}")
            return connection

    async def release(self, key: str):
        """
        释放连接（归还到池中）

        Args:
            key: 连接键
        """
        async with self._lock:
            if key in self._pool:
                pooled = self._pool[key]
                pooled.state = ConnectionState.IDLE
                pooled.last_used_at = time.monotonic()
                logger.debug(f"Released connection: {key}")

    async def remove(self, key: str):
        """
        移除连接（从池中删除并关闭）

        Args:
            key: 连接键
        """
        async with self._lock:
            if key in self._pool:
                pooled = self._pool[key]
                await self._close_connection(pooled)
                del self._pool[key]
                logger.debug(f"Removed connection: {key}")

    async def _close_connection(self, pooled: PooledConnection):
        """关闭连接"""
        try:
            if hasattr(pooled.connection, "close"):
                await pooled.connection.close()
            pooled.state = ConnectionState.CLOSED
            self._stats["total_closed"] += 1
        except Exception as e:
            logger.warning(f"Failed to close connection: {e}")

    async def _cleanup_expired(self):
        """清理过期连接"""
        now = time.monotonic()
        keys_to_remove = []

        for key, pooled in self._pool.items():
            if pooled.state != ConnectionState.IDLE:
                continue

            # 检查是否过期
            if now - pooled.created_at > self.max_lifetime:
                keys_to_remove.append(key)
            elif now - pooled.last_used_at > self.max_idle_time:
                keys_to_remove.append(key)

        for key in keys_to_remove:
            pooled = self._pool[key]
            await self._close_connection(pooled)
            del self._pool[key]
            logger.debug(f"Cleaned up expired connection: {key}")

    async def _health_check_loop(self):
        """健康检查循环"""
        while not self._closed:
            try:
                await asyncio.sleep(self.health_check_interval)
                await self._health_check()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Health check error: {e}")

    async def _health_check(self):
        """执行健康检查"""
        async with self._lock:
            keys_to_remove = []

            for key, pooled in self._pool.items():
                if pooled.state != ConnectionState.IDLE:
                    continue

                # 检查连接是否仍然有效
                try:
                    if hasattr(pooled.connection, "ping"):
                        await asyncio.wait_for(
                            pooled.connection.ping(),
                            timeout=5.0,
                        )
                except Exception as e:
                    logger.warning(f"Health check failed for {key}: {e}")
                    keys_to_remove.append(key)
                    self._stats["total_health_check_failures"] += 1

            for key in keys_to_remove:
                pooled = self._pool[key]
                await self._close_connection(pooled)
                del self._pool[key]
                logger.debug(f"Removed unhealthy connection: {key}")

    def get_stats(self) -> dict:
        """
        获取连接池统计信息

        Returns:
            统计信息字典
        """
        active_count = sum(
            1 for p in self._pool.values() if p.state == ConnectionState.ACTIVE
        )
        idle_count = sum(
            1 for p in self._pool.values() if p.state == ConnectionState.IDLE
        )

        return {
            "size": len(self._pool),
            "max_size": self.max_size,
            "active": active_count,
            "idle": idle_count,
            "total_created": self._stats["total_created"],
            "total_reused": self._stats["total_reused"],
            "total_closed": self._stats["total_closed"],
            "total_health_check_failures": self._stats["total_health_check_failures"],
            "max_idle_time": self.max_idle_time,
            "max_lifetime": self.max_lifetime,
        }

    def log_stats(self):
        """记录连接池统计信息到日志"""
        stats = self.get_stats()
        logger.info(
            f"WebSocket pool stats: size={stats['size']}/{stats['max_size']}, "
            f"active={stats['active']}, idle={stats['idle']}, "
            f"created={stats['total_created']}, reused={stats['total_reused']}, "
            f"closed={stats['total_closed']}"
        )


# 全局连接池实例
_ws_pool: Optional[WebSocketPool] = None


def get_websocket_pool(
    max_size: int = 10,
    max_idle_time: float = 300.0,
    max_lifetime: float = 3600.0,
) -> WebSocketPool:
    """
    获取全局 WebSocket 连接池实例

    Args:
        max_size: 连接池最大容量
        max_idle_time: 最大空闲时间（秒）
        max_lifetime: 连接最大生命周期（秒）

    Returns:
        WebSocketPool 实例
    """
    global _ws_pool
    if _ws_pool is None:
        _ws_pool = WebSocketPool(
            max_size=max_size,
            max_idle_time=max_idle_time,
            max_lifetime=max_lifetime,
        )
    return _ws_pool


__all__ = [
    "ConnectionState",
    "PooledConnection",
    "WebSocketPool",
    "get_websocket_pool",
]
