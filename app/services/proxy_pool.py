"""
Dynamic proxy pool helpers.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, Awaitable, Callable, Optional

import httpx
import orjson

from app.core.config import get_config
from app.core.logger import logger


class ProxyPool:
    """Manage static proxy settings and optional dynamic proxy pool refresh."""

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._current_proxy: Optional[str] = None
        self._last_refresh_at = 0.0
        self._refresh_task: Optional[asyncio.Task] = None

    @staticmethod
    def _normalize_proxy(value: Any) -> Optional[str]:
        if not value:
            return None
        if isinstance(value, bytes):
            value = value.decode("utf-8", errors="ignore")
        if not isinstance(value, str):
            return None

        candidate = value.strip()
        if not candidate:
            return None

        candidate = candidate.splitlines()[0].strip()
        if not candidate:
            return None

        if "//" not in candidate:
            candidate = f"http://{candidate}"

        if not candidate.startswith(("http://", "https://", "socks5://", "socks5h://", "socks4://", "socks4a://")):
            return None

        return candidate

    @staticmethod
    def _extract_proxy(payload: Any) -> Optional[str]:
        if isinstance(payload, str):
            text = payload.strip()
            if not text:
                return None

            # Try plain proxy string first.
            normalized = ProxyPool._normalize_proxy(text)
            if normalized:
                return normalized

            # Try JSON payload string.
            try:
                decoded = orjson.loads(text)
            except Exception:
                return None
            return ProxyPool._extract_proxy(decoded)

        if isinstance(payload, list):
            for item in payload:
                proxy = ProxyPool._extract_proxy(item)
                if proxy:
                    return proxy
            return None

        if isinstance(payload, dict):
            for key in (
                "proxy",
                "proxy_url",
                "url",
                "http",
                "https",
                "result",
                "data",
                "ip",
            ):
                if key not in payload:
                    continue
                proxy = ProxyPool._extract_proxy(payload.get(key))
                if proxy:
                    return proxy
        return None

    @staticmethod
    def _get_static_proxy(for_asset: bool = False) -> str:
        if for_asset:
            return str(get_config("proxy.asset_proxy_url") or "").strip()
        return str(get_config("proxy.base_proxy_url") or "").strip()

    @staticmethod
    def _get_pool_url() -> str:
        return str(get_config("proxy.pool_url") or "").strip()

    @staticmethod
    def _get_refresh_seconds() -> float:
        value = get_config("proxy.pool_refresh_sec", 300)
        try:
            return max(1.0, float(value))
        except Exception:
            return 300.0

    def _should_refresh(self) -> bool:
        refresh_sec = self._get_refresh_seconds()
        if not self._current_proxy:
            return True
        return (time.monotonic() - self._last_refresh_at) >= refresh_sec

    async def _fetch_pool_proxy(self, pool_url: str) -> Optional[str]:
        timeout = httpx.Timeout(10.0, connect=5.0)
        headers = {
            "User-Agent": str(get_config("proxy.user_agent") or "grok2api-proxy-pool"),
            "Accept": "application/json, text/plain, */*",
        }

        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            response = await client.get(pool_url, headers=headers)
            if response.status_code != 200:
                logger.warning(
                    f"Proxy pool fetch failed: status={response.status_code}",
                    extra={"pool_url": pool_url},
                )
                return None

            text = response.text.strip()
            if not text:
                return None

            proxy = self._extract_proxy(text)
            if proxy:
                return proxy

            # Fall back to direct response body inspection for odd payloads.
            return self._normalize_proxy(text)

    async def refresh(self, *, force: bool = False) -> Optional[str]:
        pool_url = self._get_pool_url()
        if not pool_url:
            self._current_proxy = None
            self._last_refresh_at = 0.0
            return None

        if not force and not self._should_refresh():
            return self._current_proxy

        async with self._lock:
            if not force and not self._should_refresh():
                return self._current_proxy

            try:
                proxy = await self._fetch_pool_proxy(pool_url)
                self._last_refresh_at = time.monotonic()
                if proxy:
                    if proxy != self._current_proxy:
                        logger.info(f"Proxy pool switched proxy: {proxy}")
                    self._current_proxy = proxy
                else:
                    logger.warning("Proxy pool returned no valid proxy; keep previous proxy")
                return self._current_proxy
            except Exception as e:
                self._last_refresh_at = time.monotonic()
                logger.warning(f"Proxy pool refresh error: {e}")
                return self._current_proxy

    async def _refresh_loop(self):
        while True:
            try:
                await asyncio.sleep(self._get_refresh_seconds())
                if not self._get_pool_url():
                    self._current_proxy = None
                    self._last_refresh_at = 0.0
                    continue
                await self.refresh(force=True)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning(f"Proxy pool background refresh error: {e}")

    async def start(self):
        if self._refresh_task is not None:
            return
        if not self._get_pool_url():
            self._current_proxy = None
            self._last_refresh_at = 0.0
            return
        await self.refresh(force=True)
        self._refresh_task = asyncio.create_task(self._refresh_loop())

    async def stop(self):
        task = self._refresh_task
        if task is None:
            return
        self._refresh_task = None
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.warning(f"Proxy pool stop error: {e}")

    async def get_proxy(self, *, for_asset: bool = False) -> Optional[str]:
        static_proxy = self._get_static_proxy(for_asset=for_asset)

        # Asset requests prefer dedicated static proxy when configured.
        if for_asset and static_proxy:
            return static_proxy

        pool_url = self._get_pool_url()
        if not pool_url:
            return static_proxy or None

        if self._should_refresh():
            await self.refresh(force=False)

        return self._current_proxy or static_proxy or None

    def get_current_proxy(self) -> Optional[str]:
        """Fast path for sync contexts (e.g. websocket connect setup)."""
        return self._current_proxy or self._get_static_proxy(for_asset=False) or None


proxy_pool = ProxyPool()


def build_proxies(proxy_url: Optional[str]) -> Optional[dict[str, str]]:
    normalized = ProxyPool._normalize_proxy(proxy_url)
    if not normalized:
        return None
    return {"http": normalized, "https": normalized}


async def get_proxy_url(*, for_asset: bool = False) -> Optional[str]:
    return await proxy_pool.get_proxy(for_asset=for_asset)


async def request_with_proxy_retry(
    request_func: Callable[[Optional[str], Optional[dict[str, str]], int], Awaitable[Any]],
) -> Any:
    """
    Retry request on 403 by forcing proxy rotation from dynamic pool.

    request_func signature: async (proxy_url, proxies, attempt_index) -> response
    """
    pool_url = str(get_config("proxy.pool_url") or "").strip()
    max_retry = get_config("proxy.pool_403_max", 5)
    try:
        max_retry = max(1, int(max_retry))
    except Exception:
        max_retry = 5

    attempts = max_retry if pool_url else 1
    last_response = None

    for attempt in range(attempts):
        proxy_url = await get_proxy_url(for_asset=False)
        proxies = build_proxies(proxy_url)
        response = await request_func(proxy_url, proxies, attempt)
        last_response = response

        status_code = getattr(response, "status_code", None)
        if status_code != 403:
            return response

        if attempt >= attempts - 1:
            return response

        logger.warning(
            f"Upstream 403, rotating proxy (attempt {attempt + 1}/{attempts})",
            extra={"proxy": proxy_url},
        )
        await proxy_pool.refresh(force=True)

    return last_response


__all__ = [
    "proxy_pool",
    "get_proxy_url",
    "build_proxies",
    "request_with_proxy_retry",
]
