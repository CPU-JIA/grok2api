"""请求日志审计"""

import asyncio
import time
from collections import deque
from typing import Deque, Dict, List

from app.core.config import get_config
from app.core.logger import logger
from app.core.storage import get_storage


DEFAULT_LOG_MAX_LEN = 2000
DEFAULT_SAVE_DELAY_MS = 500


class RequestLogger:
    """请求日志记录器（单例）"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, "_initialized"):
            return
        self._logs: Deque[Dict] = deque(maxlen=DEFAULT_LOG_MAX_LEN)
        self._lock = asyncio.Lock()
        self._loaded = False
        self._save_task: asyncio.Task | None = None
        self._dirty = False
        self._save_delay = DEFAULT_SAVE_DELAY_MS / 1000.0
        self._initialized = True

    async def init(self):
        if self._loaded:
            return
        async with self._lock:
            if self._loaded:
                return
            storage = get_storage()
            data = await storage.load_json("logs.json", [])
            max_len = int(get_config("logs.max_len", DEFAULT_LOG_MAX_LEN))
            self._logs = deque(maxlen=max_len)
            if isinstance(data, list):
                for item in data[-max_len:]:
                    self._logs.append(item)
            self._loaded = True
            logger.info(f"RequestLogger initialized: {len(self._logs)} logs")

    def _schedule_save(self):
        delay_ms = get_config("logs.save_delay_ms", DEFAULT_SAVE_DELAY_MS)
        try:
            delay_ms = float(delay_ms)
        except Exception:
            delay_ms = float(DEFAULT_SAVE_DELAY_MS)
        self._save_delay = max(0.0, delay_ms / 1000.0)
        self._dirty = True
        if self._save_delay == 0:
            if self._save_task and not self._save_task.done():
                return
            self._save_task = asyncio.create_task(self._save())
            return
        if self._save_task and not self._save_task.done():
            return
        self._save_task = asyncio.create_task(self._flush_loop())

    async def _flush_loop(self):
        try:
            while True:
                await asyncio.sleep(self._save_delay)
                if not self._dirty:
                    break
                self._dirty = False
                await self._save()
        finally:
            self._save_task = None
            if self._dirty:
                self._schedule_save()

    async def _save(self):
        storage = get_storage()
        await storage.save_json("logs.json", list(self._logs))

    async def log(
        self,
        model: str,
        status: int,
        duration_ms: int,
        ip: str = "",
        key_name: str = "",
        key_masked: str = "",
        token_suffix: str = "",
        error: str | None = None,
        stream: bool = False,
    ):
        await self.init()
        now = time.time()
        log_item = {
            "id": str(int(now * 1000)),
            "time": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(now)),
            "timestamp": now,
            "ip": ip,
            "model": model,
            "duration": round(duration_ms / 1000.0, 3),
            "status": status,
            "key_name": key_name or key_masked or "",
            "key_masked": key_masked or "",
            "token_suffix": token_suffix or "",
            "error": error or "",
            "stream": bool(stream),
        }

        async with self._lock:
            self._logs.appendleft(log_item)
        self._schedule_save()

    async def list_logs(
        self, limit: int = 100, offset: int = 0
    ) -> Dict[str, List[Dict]]:
        await self.init()
        limit = max(1, int(limit))
        offset = max(0, int(offset))
        async with self._lock:
            data = list(self._logs)
        total = len(data)
        return {"logs": data[offset : offset + limit], "total": total}

    async def clear(self):
        await self.init()
        async with self._lock:
            self._logs.clear()
        await self._save()

    async def flush(self):
        task = self._save_task
        if task and not task.done():
            try:
                await task
            except Exception:
                pass
        await self._save()


request_logger = RequestLogger()

__all__ = ["request_logger", "RequestLogger"]
