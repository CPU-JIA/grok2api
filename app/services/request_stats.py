"""请求统计模块"""

import asyncio
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, Any

from app.core.config import get_config
from app.core.logger import logger
from app.core.storage import get_storage


DEFAULT_HOURLY_KEEP = 48
DEFAULT_DAILY_KEEP = 30
DEFAULT_SAVE_DELAY_MS = 500


class RequestStats:
    """请求统计管理器（单例）"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, "_initialized"):
            return
        self._hourly = defaultdict(lambda: {"total": 0, "success": 0, "failed": 0})
        self._daily = defaultdict(lambda: {"total": 0, "success": 0, "failed": 0})
        self._models = defaultdict(int)
        self._lock = asyncio.Lock()
        self._loaded = False
        self._save_task: asyncio.Task | None = None
        self._dirty = False
        self._save_delay = DEFAULT_SAVE_DELAY_MS / 1000.0
        self._cleanup_counter = 0
        self._cleanup_interval = 100
        self._initialized = True

    async def init(self):
        if self._loaded:
            return
        async with self._lock:
            if self._loaded:
                return
            storage = get_storage()
            data = await storage.load_json("stats.json", {})
            if isinstance(data, dict):
                self._hourly = defaultdict(
                    lambda: {"total": 0, "success": 0, "failed": 0}
                )
                self._hourly.update(data.get("hourly", {}))
                self._daily = defaultdict(
                    lambda: {"total": 0, "success": 0, "failed": 0}
                )
                self._daily.update(data.get("daily", {}))
                self._models = defaultdict(int)
                self._models.update(data.get("models", {}))
            self._loaded = True
            logger.info("RequestStats initialized")

    async def _save(self):
        storage = get_storage()
        data = {
            "hourly": dict(self._hourly),
            "daily": dict(self._daily),
            "models": dict(self._models),
        }
        await storage.save_json("stats.json", data)

    def _schedule_save(self):
        delay_ms = get_config("stats.save_delay_ms", DEFAULT_SAVE_DELAY_MS)
        try:
            delay_ms = float(delay_ms)
        except Exception:
            delay_ms = float(DEFAULT_SAVE_DELAY_MS)
        self._save_delay = max(0.0, delay_ms / 1000.0)
        self._dirty = True

        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return

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

    def _cleanup(self):
        hourly_keep = int(get_config("stats.hourly_keep", DEFAULT_HOURLY_KEEP))
        daily_keep = int(get_config("stats.daily_keep", DEFAULT_DAILY_KEEP))

        hour_keys = list(self._hourly.keys())
        if len(hour_keys) > hourly_keep:
            for key in sorted(hour_keys)[:-hourly_keep]:
                del self._hourly[key]

        day_keys = list(self._daily.keys())
        if len(day_keys) > daily_keep:
            for key in sorted(day_keys)[:-daily_keep]:
                del self._daily[key]

    async def record(self, model: str, success: bool):
        await self.init()
        now = datetime.now()
        hour_key = now.strftime("%Y-%m-%dT%H")
        day_key = now.strftime("%Y-%m-%d")

        self._hourly[hour_key]["total"] += 1
        if success:
            self._hourly[hour_key]["success"] += 1
        else:
            self._hourly[hour_key]["failed"] += 1

        self._daily[day_key]["total"] += 1
        if success:
            self._daily[day_key]["success"] += 1
        else:
            self._daily[day_key]["failed"] += 1

        if model:
            self._models[model] += 1

        self._cleanup_counter += 1
        if self._cleanup_counter >= self._cleanup_interval:
            self._cleanup_counter = 0
            self._cleanup()

        self._schedule_save()

    def get_stats(self, hours: int = 24, days: int = 7) -> Dict[str, Any]:
        now = datetime.now()
        hourly = []
        for i in range(hours - 1, -1, -1):
            dt = now - timedelta(hours=i)
            key = dt.strftime("%Y-%m-%dT%H")
            data = self._hourly.get(key, {"total": 0, "success": 0, "failed": 0})
            hourly.append(
                {"hour": dt.strftime("%H:00"), "date": dt.strftime("%m-%d"), **data}
            )

        daily = []
        for i in range(days - 1, -1, -1):
            dt = now - timedelta(days=i)
            key = dt.strftime("%Y-%m-%d")
            data = self._daily.get(key, {"total": 0, "success": 0, "failed": 0})
            daily.append({"date": dt.strftime("%m-%d"), **data})

        model_data = sorted(self._models.items(), key=lambda x: x[1], reverse=True)[:10]
        total_requests = sum(d["total"] for d in self._hourly.values())
        total_success = sum(d["success"] for d in self._hourly.values())
        total_failed = sum(d["failed"] for d in self._hourly.values())

        return {
            "hourly": hourly,
            "daily": daily,
            "models": [{"model": m, "count": c} for m, c in model_data],
            "summary": {
                "total": total_requests,
                "success": total_success,
                "failed": total_failed,
                "success_rate": round(total_success / total_requests * 100, 1)
                if total_requests > 0
                else 0,
            },
        }

    async def reset(self):
        self._hourly.clear()
        self._daily.clear()
        self._models.clear()
        self._dirty = False
        await self._save()

    async def flush(self):
        task = self._save_task
        if task and not task.done():
            try:
                await task
            except Exception:
                pass
        if self._dirty:
            self._dirty = False
            await self._save()


request_stats = RequestStats()

__all__ = ["request_stats", "RequestStats"]
