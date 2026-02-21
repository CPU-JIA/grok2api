"""
统一的重试工具类

提供可配置的重试逻辑，支持：
- 指数退避 + 抖动
- 可配置的重试次数和状态码
- 超时预算管理
- Retry-After 头支持
- 统一的错误处理
"""

import asyncio
import inspect
import random
from typing import Callable, Any, Optional, TypeVar, ParamSpec

from app.core.logger import logger
from app.core.config import get_config
from app.core.exceptions import UpstreamException

P = ParamSpec("P")
T = TypeVar("T")


class RetryConfig:
    """重试配置"""

    def __init__(
        self,
        max_retry: Optional[int] = None,
        retry_codes: Optional[list[int]] = None,
        backoff_base: Optional[float] = None,
        backoff_factor: Optional[float] = None,
        backoff_max: Optional[float] = None,
        retry_budget: Optional[float] = None,
    ):
        """
        初始化重试配置

        Args:
            max_retry: 最大重试次数（默认从配置读取）
            retry_codes: 触发重试的状态码列表（默认从配置读取）
            backoff_base: 退避基础延迟（秒，默认从配置读取）
            backoff_factor: 退避倍率（默认从配置读取）
            backoff_max: 单次重试最大延迟（秒，默认从配置读取）
            retry_budget: 总重试预算时间（秒，默认从配置读取）
        """
        self.max_retry = (
            max_retry if max_retry is not None else int(get_config("retry.max_retry"))
        )
        self.retry_codes = (
            retry_codes
            if retry_codes is not None
            else get_config("retry.retry_status_codes")
        )
        self.backoff_base = (
            backoff_base
            if backoff_base is not None
            else float(get_config("retry.retry_backoff_base"))
        )
        self.backoff_factor = (
            backoff_factor
            if backoff_factor is not None
            else float(get_config("retry.retry_backoff_factor"))
        )
        self.backoff_max = (
            backoff_max
            if backoff_max is not None
            else float(get_config("retry.retry_backoff_max"))
        )
        self.retry_budget = (
            retry_budget
            if retry_budget is not None
            else float(get_config("retry.retry_budget"))
        )


class RetryContext:
    """重试上下文，跟踪重试状态"""

    def __init__(self, config: RetryConfig):
        """
        初始化重试上下文

        Args:
            config: 重试配置
        """
        self.config = config
        self.attempt = 0
        self.last_error: Optional[Exception] = None
        self.last_status: Optional[int] = None
        self.total_delay = 0.0
        self._last_delay = config.backoff_base

    def should_retry(self, status_code: int) -> bool:
        """
        判断是否应该重试

        Args:
            status_code: HTTP 状态码

        Returns:
            是否应该重试
        """
        if self.attempt >= self.config.max_retry:
            return False
        if status_code not in self.config.retry_codes:
            return False
        if self.total_delay >= self.config.retry_budget:
            return False
        return True

    def record_error(self, status_code: int, error: Exception):
        """
        记录错误信息

        Args:
            status_code: HTTP 状态码
            error: 异常对象
        """
        self.last_status = status_code
        self.last_error = error
        self.attempt += 1

    def calculate_delay(
        self, status_code: int, retry_after: Optional[float] = None
    ) -> float:
        """
        计算退避延迟时间

        策略：
        - 如果有 Retry-After 头，优先使用
        - 429 状态码使用 decorrelated jitter
        - 其他状态码使用指数退避 + full jitter

        Args:
            status_code: HTTP 状态码
            retry_after: Retry-After 头值（秒）

        Returns:
            延迟时间（秒）
        """
        # 优先使用 Retry-After
        if retry_after is not None and retry_after > 0:
            delay = min(retry_after, self.config.backoff_max)
            self._last_delay = delay
            return delay

        # 429 使用 decorrelated jitter
        if status_code == 429:
            # decorrelated jitter: delay = random(base, last_delay * 3)
            delay = random.uniform(self.config.backoff_base, self._last_delay * 3)
            delay = min(delay, self.config.backoff_max)
            self._last_delay = delay
            return delay

        # 其他状态码使用指数退避 + full jitter
        exp_delay = self.config.backoff_base * (
            self.config.backoff_factor**self.attempt
        )
        delay = random.uniform(0, min(exp_delay, self.config.backoff_max))
        return delay

    def record_delay(self, delay: float):
        """
        记录延迟时间

        Args:
            delay: 延迟时间（秒）
        """
        self.total_delay += delay


def extract_status_code(error: Exception) -> Optional[int]:
    """
    从异常中提取 HTTP 状态码

    Args:
        error: 异常对象

    Returns:
        HTTP 状态码，如果无法提取则返回 None
    """
    if isinstance(error, UpstreamException):
        if error.details and "status" in error.details:
            return error.details["status"]
        return getattr(error, "status_code", None)
    return getattr(error, "status_code", None)


def extract_retry_after(error: Exception) -> Optional[float]:
    """
    从异常中提取 Retry-After 值

    Args:
        error: 异常对象

    Returns:
        Retry-After 值（秒），如果无法提取则返回 None
    """
    if not isinstance(error, UpstreamException):
        return None

    details = error.details or {}

    # 尝试从 details 获取
    retry_after = details.get("retry_after")
    if retry_after is not None:
        try:
            return float(retry_after)
        except (ValueError, TypeError):
            pass

    # 尝试从 headers 获取
    headers = details.get("headers", {})
    if isinstance(headers, dict):
        retry_after = headers.get("Retry-After") or headers.get("retry-after")
        if retry_after is not None:
            try:
                return float(retry_after)
            except (ValueError, TypeError):
                pass

    return None


async def retry_async(
    func: Callable[P, T],
    *args: P.args,
    config: Optional[RetryConfig] = None,
    extract_status: Optional[Callable[[Exception], Optional[int]]] = None,
    on_retry: Optional[Callable[[int, int, Exception, float], Any]] = None,
    **kwargs: P.kwargs,
) -> T:
    """
    异步函数重试装饰器

    Args:
        func: 要重试的异步函数
        *args: 函数参数
        config: 重试配置（默认使用全局配置）
        extract_status: 从异常提取状态码的函数（默认使用 extract_status_code）
        on_retry: 重试回调函数 (attempt, status_code, error, delay)，可以是同步或异步
        **kwargs: 函数关键字参数

    Returns:
        函数执行结果

    Raises:
        最后一次失败的异常

    Example:
        >>> async def fetch_data():
        ...     # 可能失败的操作
        ...     pass
        >>> result = await retry_async(fetch_data)
    """
    if config is None:
        config = RetryConfig()

    ctx = RetryContext(config)

    # 使用默认的状态码提取器
    if extract_status is None:
        extract_status = extract_status_code

    while ctx.attempt <= config.max_retry:
        try:
            result = await func(*args, **kwargs)

            # 记录成功日志
            if ctx.attempt > 0:
                logger.info(
                    f"Retry succeeded after {ctx.attempt} attempts, "
                    f"total delay: {ctx.total_delay:.2f}s"
                )

            return result

        except Exception as e:
            # 提取状态码
            status_code = extract_status(e)

            if status_code is None:
                # 无法识别为可重试错误
                logger.error(f"Non-retryable error: {e}")
                raise

            # 记录错误
            ctx.record_error(status_code, e)

            # 检查是否应该重试
            if ctx.should_retry(status_code):
                # 提取 Retry-After
                retry_after = extract_retry_after(e)

                # 计算延迟
                delay = ctx.calculate_delay(status_code, retry_after)

                # 检查是否超出预算
                if ctx.total_delay + delay > config.retry_budget:
                    logger.warning(
                        f"Retry budget exhausted: {ctx.total_delay:.2f}s + {delay:.2f}s > {config.retry_budget}s"
                    )
                    raise

                ctx.record_delay(delay)

                logger.warning(
                    f"Retry {ctx.attempt}/{config.max_retry} for status {status_code}, "
                    f"waiting {delay:.2f}s (total: {ctx.total_delay:.2f}s)"
                    + (f", Retry-After: {retry_after}s" if retry_after else "")
                )

                # 执行回调
                if on_retry:
                    result = on_retry(ctx.attempt, status_code, e, delay)
                    if inspect.isawaitable(result):
                        await result

                await asyncio.sleep(delay)
                continue
            else:
                # 不可重试或重试预算耗尽
                if status_code in config.retry_codes:
                    logger.error(
                        f"Retry exhausted after {ctx.attempt} attempts, "
                        f"last status: {status_code}, total delay: {ctx.total_delay:.2f}s"
                    )
                else:
                    logger.error(f"Non-retryable status code: {status_code}")

                raise

    # 不应该到达这里
    raise RuntimeError("Retry logic error")


def with_retry(
    config: Optional[RetryConfig] = None,
    extract_status: Optional[Callable[[Exception], Optional[int]]] = None,
    on_retry: Optional[Callable[[int, int, Exception, float], Any]] = None,
):
    """
    重试装饰器

    Args:
        config: 重试配置（默认使用全局配置）
        extract_status: 从异常提取状态码的函数
        on_retry: 重试回调函数

    Returns:
        装饰器函数

    Example:
        >>> @with_retry(config=RetryConfig(max_retry=5))
        ... async def fetch_data():
        ...     # 可能失败的操作
        ...     pass
    """

    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            return await retry_async(
                func,
                *args,
                config=config,
                extract_status=extract_status,
                on_retry=on_retry,
                **kwargs,
            )

        return wrapper

    return decorator


__all__ = [
    "RetryConfig",
    "RetryContext",
    "retry_async",
    "with_retry",
    "extract_status_code",
    "extract_retry_after",
]
