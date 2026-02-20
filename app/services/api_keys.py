"""API Key 管理服务"""

import asyncio
import secrets
import time
from typing import Dict, List, Optional

from app.core.config import get_config
from app.core.logger import logger
from app.core.storage import get_storage


DEFAULT_SAVE_DELAY_MS = 500


class ApiKeyManager:
    """API Key 管理器（多 Key + 主 Key 兼容）"""

    _instance: Optional["ApiKeyManager"] = None
    _lock = asyncio.Lock()

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, "_initialized"):
            return
        self._keys: List[Dict] = []
        self._loaded = False
        self._save_lock = asyncio.Lock()
        self._save_task: Optional[asyncio.Task] = None
        self._dirty = False
        self._save_delay = DEFAULT_SAVE_DELAY_MS / 1000.0
        self._initialized = True

    async def init(self):
        if self._loaded:
            return
        async with self.__class__._lock:
            if self._loaded:
                return
            storage = get_storage()
            data = await storage.load_json("api_keys.json", [])
            if isinstance(data, list):
                self._keys = data
            else:
                self._keys = []
            self._loaded = True
            logger.info(f"ApiKeyManager initialized: {len(self._keys)} keys")

    def _schedule_save(self):
        delay_ms = get_config("api_keys.save_delay_ms", DEFAULT_SAVE_DELAY_MS)
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
        async with self._save_lock:
            storage = get_storage()
            await storage.save_json("api_keys.json", self._keys)

    def generate_key(self) -> str:
        return f"sk-{secrets.token_urlsafe(24)}"

    def list_keys(self) -> List[Dict]:
        return list(self._keys)

    def get_stats(self) -> Dict[str, int]:
        total = len(self._keys)
        active = len([k for k in self._keys if k.get("is_active", True)])
        return {"total": total, "active": active, "disabled": total - active}

    def _find_key(self, key: str) -> Optional[Dict]:
        for item in self._keys:
            if item.get("key") == key:
                return item
        return None

    def mask_key(self, key: str) -> str:
        if not key:
            return ""
        if len(key) <= 8:
            return key
        return f"{key[:4]}...{key[-4:]}"

    async def add_key(self, name: str = "") -> Dict:
        await self.init()
        new_key = {
            "key": self.generate_key(),
            "name": name or "未命名",
            "created_at": int(time.time()),
            "is_active": True,
            "usage_count": 0,
            "last_used_at": None,
        }
        self._keys.append(new_key)
        self._schedule_save()
        return new_key

    async def batch_add_keys(self, name_prefix: str, count: int) -> List[Dict]:
        await self.init()
        count = max(1, int(count))
        keys = []
        for idx in range(count):
            name = name_prefix or "未命名"
            if count > 1:
                name = f"{name_prefix or '未命名'}-{idx + 1}"
            keys.append(
                {
                    "key": self.generate_key(),
                    "name": name,
                    "created_at": int(time.time()),
                    "is_active": True,
                    "usage_count": 0,
                    "last_used_at": None,
                }
            )
        self._keys.extend(keys)
        self._schedule_save()
        return keys

    async def delete_keys(self, keys: List[str]) -> int:
        await self.init()
        before = len(self._keys)
        key_set = set(keys or [])
        self._keys = [k for k in self._keys if k.get("key") not in key_set]
        deleted = before - len(self._keys)
        if deleted > 0:
            self._schedule_save()
        return deleted

    async def update_key(self, key: str, name: Optional[str] = None, is_active: Optional[bool] = None) -> bool:
        await self.init()
        item = self._find_key(key)
        if not item:
            return False
        if name is not None:
            item["name"] = name
        if is_active is not None:
            item["is_active"] = bool(is_active)
        self._schedule_save()
        return True

    async def record_usage(self, key: str):
        if not key:
            return
        await self.init()
        item = self._find_key(key)
        if not item:
            return
        item["usage_count"] = int(item.get("usage_count") or 0) + 1
        item["last_used_at"] = int(time.time())
        self._schedule_save()

    async def validate_key(self, key: str) -> Optional[Dict]:
        await self.init()
        item = self._find_key(key)
        if not item:
            return None
        if not item.get("is_active", True):
            return None
        return item

    async def flush(self):
        task = self._save_task
        if task and not task.done():
            try:
                await task
            except Exception:
                pass
        if self._dirty:
            await self._save()


api_key_manager = ApiKeyManager()

__all__ = ["api_key_manager", "ApiKeyManager"]
