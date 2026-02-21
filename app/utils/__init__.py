"""
Utility modules for Grok2API.

This package contains utility modules for common functionality:
- retry: Unified retry logic with exponential backoff
- constants: Centralized constant definitions
- token_cache: LRU cache for token selection
- circuit_breaker: Circuit breaker pattern for fault tolerance
- websocket_pool: WebSocket connection pooling
- distributed_cache: Distributed caching with Redis support
"""

from app.utils.retry import (
    RetryConfig,
    RetryContext,
    retry_async,
    with_retry,
    extract_status_code,
    extract_retry_after,
)
from app.utils.constants import (
    TokenQuota,
    TimeoutConstants,
    ImageThresholds,
    ConcurrencyLimits,
    BatchSizes,
    CacheLimits,
    RetryDefaults,
    TokenManagement,
    ConversationDefaults,
    StatsDefaults,
    LogsDefaults,
    ProxyDefaults,
    SessionDefaults,
    HTTPDefaults,
    APIDefaults,
)
from app.utils.token_cache import TokenCache, get_token_cache
from app.utils.circuit_breaker import (
    CircuitState,
    CircuitBreakerConfig,
    CircuitBreakerStats,
    CircuitBreaker,
    CircuitBreakerOpenError,
    get_circuit_breaker,
    with_circuit_breaker,
)
from app.utils.websocket_pool import (
    ConnectionState,
    PooledConnection,
    WebSocketPool,
    get_websocket_pool,
)
from app.utils.distributed_cache import (
    DistributedCache,
    get_distributed_cache,
    cached,
)

__all__ = [
    # Retry utilities
    "RetryConfig",
    "RetryContext",
    "retry_async",
    "with_retry",
    "extract_status_code",
    "extract_retry_after",
    # Constants
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
    # Token cache
    "TokenCache",
    "get_token_cache",
    # Circuit breaker
    "CircuitState",
    "CircuitBreakerConfig",
    "CircuitBreakerStats",
    "CircuitBreaker",
    "CircuitBreakerOpenError",
    "get_circuit_breaker",
    "with_circuit_breaker",
    # WebSocket pool
    "ConnectionState",
    "PooledConnection",
    "WebSocketPool",
    "get_websocket_pool",
    # Distributed cache
    "DistributedCache",
    "get_distributed_cache",
    "cached",
]
