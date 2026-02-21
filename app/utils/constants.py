"""
集中化常量定义

将代码中散落的魔法数字集中管理，提高可维护性。
"""


class TokenQuota:
    """Token 配额常量"""

    # 基础账号配额
    BASIC_QUOTA = 80
    BASIC_REFRESH_HOURS = 20

    # Super 账号配额
    SUPER_QUOTA = 140
    SUPER_REFRESH_HOURS = 2

    # 努力消耗
    EFFORT_LOW = 1
    EFFORT_HIGH = 4


class TimeoutConstants:
    """超时时间常量（秒）"""

    # 通用超时
    DEFAULT_TIMEOUT = 60
    LONG_TIMEOUT = 120
    VERY_LONG_TIMEOUT = 600

    # Chat 超时
    CHAT_TIMEOUT = 60
    CHAT_STREAM_IDLE = 120
    CHAT_STREAM_FIRST = 30
    CHAT_STREAM_TOTAL = 600

    # Image 超时
    IMAGE_TIMEOUT = 60
    IMAGE_STREAM_IDLE = 120
    IMAGE_STREAM_FIRST = 30
    IMAGE_STREAM_TOTAL = 600
    IMAGE_FINAL_WAIT = 15

    # Video 超时
    VIDEO_TIMEOUT = 60
    VIDEO_STREAM_IDLE = 120
    VIDEO_STREAM_FIRST = 30
    VIDEO_STREAM_TOTAL = 600

    # Voice 超时
    VOICE_TIMEOUT = 120

    # Asset 操作超时
    ASSET_UPLOAD_TIMEOUT = 60
    ASSET_DOWNLOAD_TIMEOUT = 60
    ASSET_LIST_TIMEOUT = 60
    ASSET_DELETE_TIMEOUT = 60

    # NSFW 操作超时
    NSFW_TIMEOUT = 60

    # Usage 操作超时
    USAGE_TIMEOUT = 60


class ImageThresholds:
    """图片质量阈值（字节）"""

    # 中等质量图最小字节数
    MEDIUM_MIN_BYTES = 30_000

    # 最终图最小字节数（通常 JPG > 100KB）
    FINAL_MIN_BYTES = 100_000


class ConcurrencyLimits:
    """并发限制"""

    # Chat 并发
    CHAT_CONCURRENT = 50

    # Video 并发
    VIDEO_CONCURRENT = 100

    # Asset 操作并发
    ASSET_UPLOAD_CONCURRENT = 100
    ASSET_DOWNLOAD_CONCURRENT = 100
    ASSET_LIST_CONCURRENT = 100
    ASSET_DELETE_CONCURRENT = 100

    # NSFW 批量操作并发
    NSFW_CONCURRENT = 60

    # Usage 批量操作并发
    USAGE_CONCURRENT = 100


class BatchSizes:
    """批量操作批次大小"""

    # Asset 操作批次
    ASSET_LIST_BATCH = 50
    ASSET_DELETE_BATCH = 50

    # NSFW 批量操作批次
    NSFW_BATCH = 30

    # Usage 批量操作批次
    USAGE_BATCH = 50


class CacheLimits:
    """缓存限制"""

    # 缓存大小上限（MB）
    DEFAULT_CACHE_LIMIT_MB = 512

    # 缓存大小上限（字节）
    DEFAULT_CACHE_LIMIT_BYTES = 512 * 1024 * 1024


class RetryDefaults:
    """重试默认值"""

    # 最大重试次数
    MAX_RETRY = 3

    # 触发重试的状态码
    RETRY_STATUS_CODES = [401, 429, 403]

    # 触发重建 session 的状态码
    RESET_SESSION_STATUS_CODES = [403]

    # 退避基础延迟（秒）
    BACKOFF_BASE = 0.5

    # 退避倍率
    BACKOFF_FACTOR = 2.0

    # 单次重试最大延迟（秒）
    BACKOFF_MAX = 20.0

    # 总重试预算时间（秒）
    RETRY_BUDGET = 60.0


class TokenManagement:
    """Token 管理常量"""

    # Token 连续失败阈值
    FAIL_THRESHOLD = 5

    # Token 变更保存延迟（毫秒）
    SAVE_DELAY_MS = 500

    # 使用量写入最小间隔（秒）
    USAGE_FLUSH_INTERVAL_SEC = 5

    # 多 worker 状态同步间隔（秒）
    RELOAD_INTERVAL_SEC = 30

    # 普通错误次数冷却（请求次数）
    COOLDOWN_ERROR_REQUESTS = 5

    # 429 有额度冷却（秒）
    COOLDOWN_429_QUOTA_SEC = 3600

    # 429 无额度冷却（秒）
    COOLDOWN_429_EMPTY_SEC = 36000


class ConversationDefaults:
    """会话管理默认值"""

    # 会话过期时间（秒）
    TTL_SECONDS = 86400  # 24 小时

    # 每个 Token 最多保留会话数
    MAX_PER_TOKEN = 50

    # 自动清理间隔（秒）
    CLEANUP_INTERVAL_SEC = 600  # 10 分钟

    # 会话落盘合并延迟（毫秒）
    SAVE_DELAY_MS = 500


class StatsDefaults:
    """统计默认值"""

    # 小时统计保留数量
    HOURLY_KEEP = 48

    # 天统计保留数量
    DAILY_KEEP = 30

    # 统计写入合并延迟（毫秒）
    SAVE_DELAY_MS = 500


class LogsDefaults:
    """日志默认值"""

    # 日志保留条数
    MAX_LEN = 2000

    # 日志保存延迟（毫秒）
    SAVE_DELAY_MS = 500


class ProxyDefaults:
    """代理默认值"""

    # 代理池刷新间隔（秒）
    POOL_REFRESH_SEC = 300  # 5 分钟

    # 403 代理池重试次数
    POOL_403_MAX = 5


class SessionDefaults:
    """会话默认值"""

    # 后台会话有效期（小时）
    ADMIN_SESSION_TTL_HOURS = 24

    # Public 会话有效期（小时）
    PUBLIC_SESSION_TTL_HOURS = 24


class HTTPDefaults:
    """HTTP 默认值"""

    # 默认 User-Agent
    DEFAULT_USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36"

    # 默认浏览器指纹
    DEFAULT_BROWSER = "chrome136"


class APIDefaults:
    """API 默认值"""

    # 默认温度
    DEFAULT_TEMPERATURE = 0.8

    # 默认 top_p
    DEFAULT_TOP_P = 0.95

    # 默认流式响应
    DEFAULT_STREAM = True

    # 默认思维链输出
    DEFAULT_THINKING = True


__all__ = [
    "TokenQuota",
    "TimeoutConstants",
    "ImageThresholds",
    "ConcurrencyLimits",
    "BatchSizes",
    "CacheLimits",
    "RetryDefaults",
    "TokenManagement",
    "ConversationDefaults",
    "StatsDefaults",
    "LogsDefaults",
    "ProxyDefaults",
    "SessionDefaults",
    "HTTPDefaults",
    "APIDefaults",
]
