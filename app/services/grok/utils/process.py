"""
响应处理器基类和通用工具
"""

import asyncio
import time
from typing import Any, AsyncGenerator, Optional, AsyncIterable, List, TypeVar

from app.core.config import get_config
from app.core.logger import logger
from app.core.exceptions import (
    StreamIdleTimeoutError,
    StreamFirstTimeoutError,
    StreamTotalTimeoutError,
)
from app.services.grok.utils.download import DownloadService


T = TypeVar("T")


def _is_http2_error(e: Exception) -> bool:
    """检查是否为 HTTP/2 流错误"""
    err_str = str(e).lower()
    return "http/2" in err_str or "curl: (92)" in err_str or "stream" in err_str


def _normalize_line(line: Any) -> Optional[str]:
    """规范化流式响应行，兼容 SSE data 前缀与空行"""
    if line is None:
        return None
    if isinstance(line, (bytes, bytearray)):
        text = line.decode("utf-8", errors="ignore")
    else:
        text = str(line)
    text = text.strip()
    if not text:
        return None
    if text.startswith("data:"):
        text = text[5:].strip()
    if text == "[DONE]":
        return None
    return text


def _collect_images(obj: Any) -> List[str]:
    """递归收集响应中的图片 URL"""
    urls: List[str] = []
    seen = set()

    def add(url: str):
        if not url or url in seen:
            return
        seen.add(url)
        urls.append(url)

    def walk(value: Any):
        if isinstance(value, dict):
            for key, item in value.items():
                if key in {"generatedImageUrls", "imageUrls", "imageURLs"}:
                    if isinstance(item, list):
                        for url in item:
                            if isinstance(url, str):
                                add(url)
                    elif isinstance(item, str):
                        add(item)
                    continue
                walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)

    walk(obj)
    return urls


async def _with_idle_timeout(
    iterable: AsyncIterable[T], idle_timeout: float, model: str = ""
) -> AsyncGenerator[T, None]:
    """
    包装异步迭代器，添加空闲超时检测

    Args:
        iterable: 原始异步迭代器
        idle_timeout: 空闲超时时间(秒)，0 表示禁用
        model: 模型名称(用于日志)
    """
    if idle_timeout <= 0:
        async for item in iterable:
            yield item
        return

    iterator = iterable.__aiter__()

    async def _maybe_aclose(it):
        aclose = getattr(it, "aclose", None)
        if not aclose:
            return
        try:
            await aclose()
        except Exception:
            pass

    while True:
        try:
            item = await asyncio.wait_for(iterator.__anext__(), timeout=idle_timeout)
            yield item
        except asyncio.TimeoutError:
            logger.warning(
                f"Stream idle timeout after {idle_timeout}s",
                extra={"model": model, "idle_timeout": idle_timeout},
            )
            await _maybe_aclose(iterator)
            raise StreamIdleTimeoutError(idle_timeout)
        except asyncio.CancelledError:
            await _maybe_aclose(iterator)
            raise
        except StopAsyncIteration:
            break


async def _with_stream_timeouts(
    iterable: AsyncIterable[T],
    *,
    first_timeout: float = 0.0,
    idle_timeout: float = 0.0,
    total_timeout: float = 0.0,
    model: str = "",
) -> AsyncGenerator[T, None]:
    """
    包装异步迭代器，添加首次响应、空闲与总时长超时
    """
    if first_timeout <= 0 and idle_timeout <= 0 and total_timeout <= 0:
        async for item in iterable:
            yield item
        return

    iterator = iterable.__aiter__()
    start_time = time.monotonic()
    is_first = True

    async def _maybe_aclose(it):
        aclose = getattr(it, "aclose", None)
        if not aclose:
            return
        try:
            await aclose()
        except Exception:
            pass

    while True:
        stage_timeout = None
        if is_first and first_timeout > 0:
            stage_timeout = first_timeout
        elif idle_timeout > 0:
            stage_timeout = idle_timeout

        total_remaining = None
        if total_timeout > 0:
            total_remaining = total_timeout - (time.monotonic() - start_time)
            if total_remaining <= 0:
                await _maybe_aclose(iterator)
                raise StreamTotalTimeoutError(total_timeout)

        effective_timeout = stage_timeout
        total_is_limit = False
        if total_remaining is not None:
            if effective_timeout is None or effective_timeout <= 0:
                effective_timeout = total_remaining
                total_is_limit = True
            elif total_remaining < effective_timeout:
                effective_timeout = total_remaining
                total_is_limit = True

        try:
            if effective_timeout is not None and effective_timeout > 0:
                item = await asyncio.wait_for(
                    iterator.__anext__(), timeout=effective_timeout
                )
            else:
                item = await iterator.__anext__()
            yield item
            is_first = False
        except asyncio.TimeoutError:
            if total_is_limit and total_timeout > 0:
                logger.warning(
                    f"Stream total timeout after {total_timeout}s",
                    extra={"model": model, "total_timeout": total_timeout},
                )
                await _maybe_aclose(iterator)
                raise StreamTotalTimeoutError(total_timeout)
            if is_first and first_timeout > 0:
                logger.warning(
                    f"Stream first response timeout after {first_timeout}s",
                    extra={"model": model, "first_timeout": first_timeout},
                )
                await _maybe_aclose(iterator)
                raise StreamFirstTimeoutError(first_timeout)
            logger.warning(
                f"Stream idle timeout after {idle_timeout}s",
                extra={"model": model, "idle_timeout": idle_timeout},
            )
            await _maybe_aclose(iterator)
            raise StreamIdleTimeoutError(idle_timeout)
        except asyncio.CancelledError:
            await _maybe_aclose(iterator)
            raise
        except StopAsyncIteration:
            break


class BaseProcessor:
    """基础处理器"""

    def __init__(self, model: str, token: str = ""):
        self.model = model
        self.token = token
        self.created = int(time.time())
        self.app_url = get_config("app.app_url")
        self._dl_service: Optional[DownloadService] = None

    def _get_dl(self) -> DownloadService:
        """获取下载服务实例（复用）"""
        if self._dl_service is None:
            self._dl_service = DownloadService()
        return self._dl_service

    async def close(self):
        """释放下载服务资源"""
        if self._dl_service:
            await self._dl_service.close()
            self._dl_service = None

    async def process_url(self, path: str, media_type: str = "image") -> str:
        """处理资产 URL"""
        dl_service = self._get_dl()
        return await dl_service.resolve_url(path, self.token, media_type)


__all__ = [
    "BaseProcessor",
    "_with_idle_timeout",
    "_with_stream_timeouts",
    "_normalize_line",
    "_collect_images",
    "_is_http2_error",
]
