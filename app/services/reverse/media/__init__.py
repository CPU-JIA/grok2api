"""
Media domain reverse proxy services (images, videos, assets).
"""

from app.services.reverse.ws_imagine import ImagineWebSocketReverse as WsImagineReverse
from app.services.reverse.video_upscale import VideoUpscaleReverse
from app.services.reverse.media_post import MediaPostReverse
from app.services.reverse.assets_upload import AssetsUploadReverse
from app.services.reverse.assets_download import AssetsDownloadReverse
from app.services.reverse.assets_list import AssetsListReverse
from app.services.reverse.assets_delete import AssetsDeleteReverse
from app.services.reverse.ws_livekit import LivekitTokenReverse, LivekitWebSocketReverse

# Alias for backward compatibility
WsLivekitReverse = LivekitWebSocketReverse

__all__ = [
    "WsImagineReverse",
    "VideoUpscaleReverse",
    "MediaPostReverse",
    "AssetsUploadReverse",
    "AssetsDownloadReverse",
    "AssetsListReverse",
    "AssetsDeleteReverse",
    "LivekitTokenReverse",
    "LivekitWebSocketReverse",
    "WsLivekitReverse",
]
