"""Authentication helpers and dependencies."""

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from typing import Mapping, Optional

from fastapi import HTTPException, Request, Response, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import get_config
from app.services.api_keys import api_key_manager

DEFAULT_API_KEY = ""
DEFAULT_APP_KEY = "grok2api"
DEFAULT_PUBLIC_KEY = ""
DEFAULT_PUBLIC_ENABLED = False

ADMIN_SESSION_COOKIE = "grok2api_admin_session"
PUBLIC_SESSION_COOKIE = "grok2api_public_session"
DEFAULT_ADMIN_SESSION_TTL_HOURS = 24
DEFAULT_PUBLIC_SESSION_TTL_HOURS = 24

security = HTTPBearer(
    auto_error=False,
    scheme_name="API Key",
    description="Enter your API Key in the format: Bearer <key>",
)


def get_admin_api_key() -> str:
    api_key = get_config("app.api_key", DEFAULT_API_KEY)
    return str(api_key or "")


def get_app_key() -> str:
    app_key = get_config("app.app_key", DEFAULT_APP_KEY)
    return str(app_key or "")


def get_public_api_key() -> str:
    public_key = get_config("app.public_key", DEFAULT_PUBLIC_KEY)
    return str(public_key or "")


def is_public_enabled() -> bool:
    return bool(get_config("app.public_enabled", DEFAULT_PUBLIC_ENABLED))


def _constant_time_equals(left: str, right: str) -> bool:
    if not left or not right:
        return False
    try:
        return secrets.compare_digest(str(left), str(right))
    except Exception:
        return str(left) == str(right)


def is_valid_app_key(value: Optional[str]) -> bool:
    app_key = get_app_key()
    if not app_key:
        return False
    return _constant_time_equals(str(value or ""), app_key)


def _base64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _base64url_decode(value: str) -> bytes:
    pad = "=" * ((4 - len(value) % 4) % 4)
    return base64.urlsafe_b64decode((value + pad).encode("ascii"))


def _session_secret() -> bytes:
    """获取会话签名密钥

    优先级：
    1. 环境变量 GROK2API_SESSION_SECRET
    2. 配置文件 app.session_secret
    3. 如果都未配置，抛出错误（不再回退到 app_key）
    """
    env_secret = os.getenv("GROK2API_SESSION_SECRET", "").strip()
    cfg_secret = str(get_config("app.session_secret", "") or "").strip()
    secret = env_secret or cfg_secret

    if not secret:
        # 不再回退到 app_key，强制配置 session_secret
        raise RuntimeError(
            "session_secret not configured! "
            "Please set app.session_secret in config.toml or GROK2API_SESSION_SECRET environment variable."
        )

    return secret.encode("utf-8")


def _session_ttl_seconds(kind: str) -> int:
    if kind == "admin":
        raw = get_config("app.admin_session_ttl_hours", DEFAULT_ADMIN_SESSION_TTL_HOURS)
        default_hours = DEFAULT_ADMIN_SESSION_TTL_HOURS
    else:
        raw = get_config(
            "app.public_session_ttl_hours", DEFAULT_PUBLIC_SESSION_TTL_HOURS
        )
        default_hours = DEFAULT_PUBLIC_SESSION_TTL_HOURS

    try:
        hours = float(raw)
    except (TypeError, ValueError):
        hours = float(default_hours)

    hours = max(1.0 / 6.0, hours)  # at least 10 minutes
    return int(hours * 3600)


def _sign_payload(payload_b64: str) -> str:
    signature = hmac.new(
        _session_secret(),
        payload_b64.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    return _base64url_encode(signature)


def _build_session_token(subject: str, ttl_seconds: int) -> str:
    now = int(time.time())
    payload = {
        "sub": subject,
        "iat": now,
        "exp": now + max(600, int(ttl_seconds)),
        "v": 1,
    }
    payload_json = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode(
        "utf-8"
    )
    payload_b64 = _base64url_encode(payload_json)
    return f"{payload_b64}.{_sign_payload(payload_b64)}"


def _decode_session_token(
    token: Optional[str], expected_subject: str
) -> Optional[dict]:
    if not token or "." not in token:
        return None

    payload_b64, signature = token.split(".", 1)
    expected_sig = _sign_payload(payload_b64)
    if not _constant_time_equals(signature, expected_sig):
        return None

    try:
        payload_raw = _base64url_decode(payload_b64)
        payload = json.loads(payload_raw.decode("utf-8"))
    except Exception:
        return None

    if not isinstance(payload, dict):
        return None

    if payload.get("sub") != expected_subject:
        return None

    now = int(time.time())
    try:
        exp = int(payload.get("exp") or 0)
        iat = int(payload.get("iat") or 0)
    except Exception:
        return None

    if exp <= now:
        return None

    if iat > now + 60:
        return None

    return payload


def _request_is_secure(request: Request) -> bool:
    if request.url.scheme == "https":
        return True
    forwarded_proto = (
        (request.headers.get("x-forwarded-proto") or "").split(",")[0].strip().lower()
    )
    return forwarded_proto == "https"


def _set_session_cookie(
    response: Response, request: Request, cookie_name: str, token: str, max_age: int
) -> None:
    response.set_cookie(
        key=cookie_name,
        value=token,
        max_age=max_age,
        expires=max_age,
        httponly=True,
        secure=_request_is_secure(request),
        samesite="lax",
        path="/",
    )


def _clear_session_cookie(response: Response, cookie_name: str) -> None:
    response.delete_cookie(key=cookie_name, path="/")


def set_admin_session_cookie(response: Response, request: Request) -> None:
    ttl = _session_ttl_seconds("admin")
    token = _build_session_token("admin", ttl)
    _set_session_cookie(response, request, ADMIN_SESSION_COOKIE, token, ttl)


def clear_admin_session_cookie(response: Response) -> None:
    _clear_session_cookie(response, ADMIN_SESSION_COOKIE)


def set_public_session_cookie(response: Response, request: Request) -> None:
    ttl = _session_ttl_seconds("public")
    token = _build_session_token("public", ttl)
    _set_session_cookie(response, request, PUBLIC_SESSION_COOKIE, token, ttl)


def clear_public_session_cookie(response: Response) -> None:
    _clear_session_cookie(response, PUBLIC_SESSION_COOKIE)


def has_valid_admin_session(cookies: Optional[Mapping[str, str]]) -> bool:
    if not cookies:
        return False
    token = cookies.get(ADMIN_SESSION_COOKIE)
    return _decode_session_token(token, "admin") is not None


def has_valid_public_session(cookies: Optional[Mapping[str, str]]) -> bool:
    if not cookies:
        return False
    token = cookies.get(PUBLIC_SESSION_COOKIE)
    return _decode_session_token(token, "public") is not None


def has_public_access(
    raw_key: Optional[str] = None, cookies: Optional[Mapping[str, str]] = None
) -> bool:
    # Admin session always grants public access.
    if has_valid_admin_session(cookies):
        return True

    if has_valid_public_session(cookies):
        return True

    if is_valid_app_key(raw_key):
        return True

    public_key = get_public_api_key()
    if not public_key:
        return is_public_enabled()

    return _constant_time_equals(str(raw_key or ""), public_key)


async def verify_api_key(
    request: Request,
    auth: Optional[HTTPAuthorizationCredentials] = Security(security),
) -> Optional[str]:
    provided = auth.credentials if auth else ""

    # Web UI session cookies can access OpenAI-compatible endpoints.
    if has_valid_admin_session(request.cookies) or has_valid_public_session(
        request.cookies
    ):
        return "session"

    # Public mode can also access OpenAI-compatible endpoints.
    if has_public_access(provided, request.cookies):
        return provided or "public"

    api_key = get_admin_api_key()
    await api_key_manager.init()
    has_keys = bool(api_key_manager.list_keys())
    if not api_key and not has_keys:
        return None

    if not auth:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if api_key and _constant_time_equals(provided, api_key):
        return provided

    key_info = await api_key_manager.validate_key(provided)
    if not key_info:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return provided


async def verify_app_key(
    request: Request,
    auth: Optional[HTTPAuthorizationCredentials] = Security(security),
) -> Optional[str]:
    app_key = get_app_key()

    if not app_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="App key is not configured",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Prefer explicit bearer credentials for API clients.
    if auth and _constant_time_equals(auth.credentials, app_key):
        return auth.credentials

    # Browser admin session cookie.
    if has_valid_admin_session(request.cookies):
        return "session"

    # Legacy SSE query support for /batch/*/stream only.
    if request.url.path.endswith("/stream"):
        legacy_query_key = (request.query_params.get("app_key") or "").strip()
        if _constant_time_equals(legacy_query_key, app_key):
            return legacy_query_key

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid authentication token",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def verify_public_key(
    request: Request,
    auth: Optional[HTTPAuthorizationCredentials] = Security(security),
) -> Optional[str]:
    provided = auth.credentials if auth else ""
    if has_public_access(provided, request.cookies):
        return provided or None

    # Legacy query support for SSE/WS style HTTP requests.
    legacy_query_key = (request.query_params.get("public_key") or "").strip()
    if legacy_query_key and has_public_access(legacy_query_key, request.cookies):
        return legacy_query_key

    public_key = get_public_api_key()
    if not public_key:
        if is_public_enabled():
            return None
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Public access is disabled",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not auth and not legacy_query_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid authentication token",
        headers={"WWW-Authenticate": "Bearer"},
    )


__all__ = [
    "ADMIN_SESSION_COOKIE",
    "PUBLIC_SESSION_COOKIE",
    "clear_admin_session_cookie",
    "clear_public_session_cookie",
    "get_admin_api_key",
    "get_app_key",
    "get_public_api_key",
    "has_public_access",
    "has_valid_admin_session",
    "has_valid_public_session",
    "is_public_enabled",
    "is_valid_app_key",
    "set_admin_session_cookie",
    "set_public_session_cookie",
    "verify_api_key",
    "verify_app_key",
    "verify_public_key",
]
