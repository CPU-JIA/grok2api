"""
Local cache utilities with TTL support.
"""

import time
from typing import Any, Dict, Optional
from pathlib import Path

from app.core.storage import DATA_DIR
from app.core.logger import logger

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}
VIDEO_EXTS = {".mp4", ".mov", ".m4v", ".webm", ".avi", ".mkv"}


class CacheService:
    """Local cache service with TTL support."""

    def __init__(self, default_ttl: Optional[float] = None):
        """
        初始化缓存服务

        Args:
            default_ttl: 默认 TTL（秒），None 表示永不过期
        """
        base_dir = DATA_DIR / "tmp"
        self.image_dir = base_dir / "image"
        self.video_dir = base_dir / "video"
        self.image_dir.mkdir(parents=True, exist_ok=True)
        self.video_dir.mkdir(parents=True, exist_ok=True)
        self.default_ttl = default_ttl
        self._metadata_cache: Dict[str, Dict[str, Any]] = {}

    def _cache_dir(self, media_type: str):
        return self.image_dir if media_type == "image" else self.video_dir

    def _allowed_exts(self, media_type: str):
        return IMAGE_EXTS if media_type == "image" else VIDEO_EXTS

    def _get_metadata_path(self, cache_dir: Path) -> Path:
        """获取元数据文件路径"""
        return cache_dir / ".cache_metadata.json"

    def _load_metadata(self, media_type: str) -> Dict[str, Dict[str, Any]]:
        """加载缓存元数据"""
        cache_dir = self._cache_dir(media_type)
        metadata_path = self._get_metadata_path(cache_dir)

        if not metadata_path.exists():
            return {}

        try:
            import json

            with open(metadata_path, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load cache metadata: {e}")
            return {}

    def _save_metadata(self, media_type: str, metadata: Dict[str, Dict[str, Any]]):
        """保存缓存元数据"""
        cache_dir = self._cache_dir(media_type)
        metadata_path = self._get_metadata_path(cache_dir)

        try:
            import json

            with open(metadata_path, "w") as f:
                json.dump(metadata, f)
        except Exception as e:
            logger.warning(f"Failed to save cache metadata: {e}")

    def _is_expired(self, file_path: Path, metadata: Dict[str, Any]) -> bool:
        """检查文件是否过期"""
        if self.default_ttl is None:
            return False

        created_at = metadata.get("created_at")
        if created_at is None:
            # 如果没有元数据，使用文件修改时间
            try:
                created_at = file_path.stat().st_mtime
            except Exception:
                return True

        elapsed = time.time() - created_at
        ttl = metadata.get("ttl", self.default_ttl)
        if ttl is None:
            return False
        return elapsed > ttl

    def set_file_metadata(
        self,
        media_type: str,
        filename: str,
        ttl: Optional[float] = None,
        **extra_metadata,
    ):
        """
        设置文件元数据

        Args:
            media_type: 媒体类型
            filename: 文件名
            ttl: TTL（秒），None 使用默认值
            **extra_metadata: 额外的元数据
        """
        metadata = self._load_metadata(media_type)
        metadata[filename] = {
            "created_at": time.time(),
            "ttl": ttl if ttl is not None else self.default_ttl,
            **extra_metadata,
        }
        self._save_metadata(media_type, metadata)

    def cleanup_expired(self, media_type: str = "image") -> Dict[str, Any]:
        """
        清理过期文件

        Args:
            media_type: 媒体类型

        Returns:
            清理统计信息
        """
        cache_dir = self._cache_dir(media_type)
        if not cache_dir.exists():
            return {"count": 0, "size_mb": 0.0}

        metadata = self._load_metadata(media_type)
        allowed = self._allowed_exts(media_type)
        files = [
            f
            for f in cache_dir.glob("*")
            if f.is_file() and f.suffix.lower() in allowed
        ]

        count = 0
        total_size = 0

        for f in files:
            file_metadata = metadata.get(f.name, {})
            if self._is_expired(f, file_metadata):
                try:
                    size = f.stat().st_size
                    f.unlink()
                    count += 1
                    total_size += size
                    # 从元数据中删除
                    metadata.pop(f.name, None)
                    logger.debug(f"Cleaned up expired cache file: {f.name}")
                except Exception as e:
                    logger.warning(f"Failed to delete expired file {f.name}: {e}")

        # 保存更新后的元数据
        if count > 0:
            self._save_metadata(media_type, metadata)

        return {"count": count, "size_mb": round(total_size / 1024 / 1024, 2)}

    def get_stats(self, media_type: str = "image") -> Dict[str, Any]:
        cache_dir = self._cache_dir(media_type)
        if not cache_dir.exists():
            return {"count": 0, "size_mb": 0.0}

        allowed = self._allowed_exts(media_type)
        metadata = self._load_metadata(media_type)
        files = [
            f
            for f in cache_dir.glob("*")
            if f.is_file() and f.suffix.lower() in allowed
        ]

        total_size = 0
        expired_count = 0
        for f in files:
            try:
                total_size += f.stat().st_size
                file_metadata = metadata.get(f.name, {})
                if self._is_expired(f, file_metadata):
                    expired_count += 1
            except Exception:
                continue

        return {
            "count": len(files),
            "size_mb": round(total_size / 1024 / 1024, 2),
            "expired_count": expired_count,
        }

    def list_files(
        self, media_type: str = "image", page: int = 1, page_size: int = 1000
    ) -> Dict[str, Any]:
        cache_dir = self._cache_dir(media_type)
        if not cache_dir.exists():
            return {"total": 0, "page": page, "page_size": page_size, "items": []}

        allowed = self._allowed_exts(media_type)
        files = [
            f
            for f in cache_dir.glob("*")
            if f.is_file() and f.suffix.lower() in allowed
        ]

        items = []
        for f in files:
            try:
                stat = f.stat()
                items.append(
                    {
                        "name": f.name,
                        "size_bytes": stat.st_size,
                        "mtime_ms": int(stat.st_mtime * 1000),
                    }
                )
            except Exception:
                continue

        items.sort(key=lambda x: x["mtime_ms"], reverse=True)

        total = len(items)
        start = max(0, (page - 1) * page_size)
        paged = items[start : start + page_size]

        for item in paged:
            item["view_url"] = f"/v1/files/{media_type}/{item['name']}"

        return {"total": total, "page": page, "page_size": page_size, "items": paged}

    def delete_file(self, media_type: str, name: str) -> Dict[str, Any]:
        cache_dir = self._cache_dir(media_type)
        file_path = cache_dir / name.replace("/", "-")

        if file_path.exists():
            try:
                file_path.unlink()
                return {"deleted": True}
            except Exception:
                pass
        return {"deleted": False}

    def clear(self, media_type: str = "image") -> Dict[str, Any]:
        cache_dir = self._cache_dir(media_type)
        if not cache_dir.exists():
            return {"count": 0, "size_mb": 0.0}

        files = list(cache_dir.glob("*"))
        total_size = sum(f.stat().st_size for f in files if f.is_file())
        count = 0

        for f in files:
            if f.is_file():
                try:
                    f.unlink()
                    count += 1
                except Exception:
                    pass

        return {"count": count, "size_mb": round(total_size / 1024 / 1024, 2)}


__all__ = ["CacheService"]
