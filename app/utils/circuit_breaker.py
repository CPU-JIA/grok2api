"""
熔断器模式实现

为上游调用提供熔断保护，防止故障级联。

熔断器状态机：
- CLOSED（关闭）：正常工作，请求通过
- OPEN（打开）：熔断触发，请求快速失败
- HALF_OPEN（半开）：尝试恢复，允许部分请求通过

状态转换：
- CLOSED -> OPEN：失败率超过阈值
- OPEN -> HALF_OPEN：冷却时间后
- HALF_OPEN -> CLOSED：成功率达标
- HALF_OPEN -> OPEN：失败继续
"""

import asyncio
import time
from enum import Enum
from typing import Callable, Any, Optional, TypeVar, ParamSpec
from dataclasses import dataclass, field

from app.core.logger import logger
from app.core.exceptions import AppException, ErrorType

P = ParamSpec("P")
T = TypeVar("T")


class CircuitState(Enum):
    """熔断器状态"""

    CLOSED = "closed"  # 关闭状态，正常工作
    OPEN = "open"  # 打开状态，熔断触发
    HALF_OPEN = "half_open"  # 半开状态，尝试恢复


@dataclass
class CircuitBreakerConfig:
    """熔断器配置"""

    # 失败阈值（失败次数）
    failure_threshold: int = 5

    # 成功阈值（半开状态下需要的连续成功次数）
    success_threshold: int = 2

    # 超时时间（秒）
    timeout: float = 30.0

    # 冷却时间（秒，OPEN -> HALF_OPEN）
    cooldown_seconds: float = 60.0

    # 半开状态允许的请求数
    half_open_max_calls: int = 3


@dataclass
class CircuitBreakerStats:
    """熔断器统计信息"""

    state: CircuitState = CircuitState.CLOSED
    failure_count: int = 0
    success_count: int = 0
    last_failure_time: float = 0.0
    last_state_change_time: float = field(default_factory=time.monotonic)
    total_calls: int = 0
    total_failures: int = 0
    total_successes: int = 0
    total_timeouts: int = 0
    total_rejected: int = 0


class CircuitBreakerOpenError(AppException):
    """熔断器打开错误"""

    def __init__(self, message: str = "Circuit breaker is open"):
        super().__init__(
            message=message,
            error_type=ErrorType.SERVICE_UNAVAILABLE.value,
            code="circuit_breaker_open",
            status_code=503,
        )


class CircuitBreaker:
    """熔断器"""

    def __init__(
        self,
        name: str,
        config: Optional[CircuitBreakerConfig] = None,
    ):
        """
        初始化熔断器

        Args:
            name: 熔断器名称
            config: 熔断器配置
        """
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self.stats = CircuitBreakerStats()
        self._lock = asyncio.Lock()
        self._half_open_calls = 0

    async def call(
        self,
        func: Callable[P, T],
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> T:
        """
        通过熔断器调用函数

        Args:
            func: 要调用的函数
            *args: 函数参数
            **kwargs: 函数关键字参数

        Returns:
            函数执行结果

        Raises:
            CircuitBreakerOpenError: 熔断器打开时
            其他异常: 函数执行失败时
        """
        async with self._lock:
            self.stats.total_calls += 1

            # 检查熔断器状态
            if self.stats.state == CircuitState.OPEN:
                # 检查是否可以进入半开状态
                if self._should_attempt_reset():
                    self._transition_to_half_open()
                else:
                    self.stats.total_rejected += 1
                    logger.warning(
                        f"Circuit breaker '{self.name}' is OPEN, rejecting call"
                    )
                    raise CircuitBreakerOpenError()

            elif self.stats.state == CircuitState.HALF_OPEN:
                # 半开状态下限制请求数
                if self._half_open_calls >= self.config.half_open_max_calls:
                    self.stats.total_rejected += 1
                    logger.warning(
                        f"Circuit breaker '{self.name}' is HALF_OPEN, "
                        f"max calls reached, rejecting call"
                    )
                    raise CircuitBreakerOpenError()
                self._half_open_calls += 1

        # 执行函数调用
        try:
            # 添加超时控制
            result = await asyncio.wait_for(
                func(*args, **kwargs),
                timeout=self.config.timeout,
            )

            # 记录成功
            await self._on_success()
            return result

        except asyncio.TimeoutError as e:
            # 超时视为失败
            await self._on_failure()
            self.stats.total_timeouts += 1
            logger.warning(
                f"Circuit breaker '{self.name}' call timeout after {self.config.timeout}s"
            )
            raise

        except Exception as e:
            # 记录失败
            await self._on_failure()
            raise

    async def _on_success(self):
        """处理成功调用"""
        async with self._lock:
            self.stats.total_successes += 1

            if self.stats.state == CircuitState.HALF_OPEN:
                self.stats.success_count += 1
                logger.debug(
                    f"Circuit breaker '{self.name}' HALF_OPEN success "
                    f"({self.stats.success_count}/{self.config.success_threshold})"
                )

                # 达到成功阈值，关闭熔断器
                if self.stats.success_count >= self.config.success_threshold:
                    self._transition_to_closed()

            elif self.stats.state == CircuitState.CLOSED:
                # 重置失败计数
                self.stats.failure_count = 0

    async def _on_failure(self):
        """处理失败调用"""
        async with self._lock:
            self.stats.total_failures += 1
            self.stats.failure_count += 1
            self.stats.last_failure_time = time.monotonic()

            if self.stats.state == CircuitState.HALF_OPEN:
                # 半开状态下失败，立即打开熔断器
                logger.warning(
                    f"Circuit breaker '{self.name}' HALF_OPEN failed, "
                    f"transitioning to OPEN"
                )
                self._transition_to_open()

            elif self.stats.state == CircuitState.CLOSED:
                # 检查是否达到失败阈值
                if self.stats.failure_count >= self.config.failure_threshold:
                    logger.warning(
                        f"Circuit breaker '{self.name}' failure threshold reached "
                        f"({self.stats.failure_count}/{self.config.failure_threshold}), "
                        f"transitioning to OPEN"
                    )
                    self._transition_to_open()

    def _should_attempt_reset(self) -> bool:
        """检查是否应该尝试重置（OPEN -> HALF_OPEN）"""
        elapsed = time.monotonic() - self.stats.last_state_change_time
        return elapsed >= self.config.cooldown_seconds

    def _transition_to_closed(self):
        """转换到关闭状态"""
        logger.info(f"Circuit breaker '{self.name}' transitioning to CLOSED")
        self.stats.state = CircuitState.CLOSED
        self.stats.failure_count = 0
        self.stats.success_count = 0
        self.stats.last_state_change_time = time.monotonic()
        self._half_open_calls = 0

    def _transition_to_open(self):
        """转换到打开状态"""
        logger.warning(f"Circuit breaker '{self.name}' transitioning to OPEN")
        self.stats.state = CircuitState.OPEN
        self.stats.failure_count = 0
        self.stats.success_count = 0
        self.stats.last_state_change_time = time.monotonic()
        self._half_open_calls = 0

    def _transition_to_half_open(self):
        """转换到半开状态"""
        logger.info(f"Circuit breaker '{self.name}' transitioning to HALF_OPEN")
        self.stats.state = CircuitState.HALF_OPEN
        self.stats.failure_count = 0
        self.stats.success_count = 0
        self.stats.last_state_change_time = time.monotonic()
        self._half_open_calls = 0

    def get_stats(self) -> dict:
        """
        获取熔断器统计信息

        Returns:
            统计信息字典
        """
        return {
            "name": self.name,
            "state": self.stats.state.value,
            "failure_count": self.stats.failure_count,
            "success_count": self.stats.success_count,
            "total_calls": self.stats.total_calls,
            "total_successes": self.stats.total_successes,
            "total_failures": self.stats.total_failures,
            "total_timeouts": self.stats.total_timeouts,
            "total_rejected": self.stats.total_rejected,
            "last_failure_time": self.stats.last_failure_time,
            "last_state_change_time": self.stats.last_state_change_time,
            "config": {
                "failure_threshold": self.config.failure_threshold,
                "success_threshold": self.config.success_threshold,
                "timeout": self.config.timeout,
                "cooldown_seconds": self.config.cooldown_seconds,
                "half_open_max_calls": self.config.half_open_max_calls,
            },
        }

    async def reset(self):
        """手动重置熔断器到关闭状态"""
        async with self._lock:
            logger.info(f"Circuit breaker '{self.name}' manually reset to CLOSED")
            self._transition_to_closed()


# 全局熔断器注册表
_circuit_breakers: dict[str, CircuitBreaker] = {}


def get_circuit_breaker(
    name: str,
    config: Optional[CircuitBreakerConfig] = None,
) -> CircuitBreaker:
    """
    获取或创建熔断器

    Args:
        name: 熔断器名称
        config: 熔断器配置（仅在创建时使用）

    Returns:
        CircuitBreaker 实例
    """
    if name not in _circuit_breakers:
        _circuit_breakers[name] = CircuitBreaker(name, config)
    return _circuit_breakers[name]


def with_circuit_breaker(
    name: str,
    config: Optional[CircuitBreakerConfig] = None,
):
    """
    熔断器装饰器

    Args:
        name: 熔断器名称
        config: 熔断器配置

    Returns:
        装饰器函数

    Example:
        >>> @with_circuit_breaker("grok_api", CircuitBreakerConfig(failure_threshold=3))
        ... async def call_grok_api():
        ...     # 可能失败的操作
        ...     pass
    """

    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        breaker = get_circuit_breaker(name, config)

        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            return await breaker.call(func, *args, **kwargs)

        return wrapper

    return decorator


__all__ = [
    "CircuitState",
    "CircuitBreakerConfig",
    "CircuitBreakerStats",
    "CircuitBreaker",
    "CircuitBreakerOpenError",
    "get_circuit_breaker",
    "with_circuit_breaker",
]
