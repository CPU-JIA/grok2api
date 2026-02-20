"""
API 认证模块
"""

from typing import Optional
from fastapi import HTTPException, status, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.core.config import get_config
from app.services.api_keys import api_key_manager

DEFAULT_API_KEY = ""
DEFAULT_APP_KEY = "grok2api"
DEFAULT_PUBLIC_KEY = ""
DEFAULT_PUBLIC_ENABLED = False

# 定义 Bearer Scheme
security = HTTPBearer(
    auto_error=False,
    scheme_name="API Key",
    description="Enter your API Key in the format: Bearer <key>",
)


def get_admin_api_key() -> str:
    """
    获取后台 API Key。

    为空时表示不启用后台接口认证。
    """
    api_key = get_config("app.api_key", DEFAULT_API_KEY)
    return api_key or ""

def get_app_key() -> str:
    """
    获取 App Key（后台管理密码）。
    """
    app_key = get_config("app.app_key", DEFAULT_APP_KEY)
    return app_key or ""

def get_public_api_key() -> str:
    """
    获取 Public API Key。

    为空时表示不启用 public 接口认证。
    """
    public_key = get_config("app.public_key", DEFAULT_PUBLIC_KEY)
    return public_key or ""

def is_public_enabled() -> bool:
    """
    是否开启 public 功能入口。
    """
    return bool(get_config("app.public_enabled", DEFAULT_PUBLIC_ENABLED))


async def verify_api_key(
    auth: Optional[HTTPAuthorizationCredentials] = Security(security),
) -> Optional[str]:
    """
    验证 Bearer Token

    如果 config.toml 中未配置 api_key，则不启用认证。
    """
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

    if api_key and auth.credentials == api_key:
        return auth.credentials

    key_info = await api_key_manager.validate_key(auth.credentials)
    if not key_info:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return auth.credentials


async def verify_app_key(
    auth: Optional[HTTPAuthorizationCredentials] = Security(security),
) -> Optional[str]:
    """
    验证后台登录密钥（app_key）。

    app_key 必须配置，否则拒绝登录。
    """
    app_key = get_app_key()

    if not app_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="App key is not configured",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not auth:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if auth.credentials != app_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return auth.credentials


async def verify_public_key(
    auth: Optional[HTTPAuthorizationCredentials] = Security(security),
) -> Optional[str]:
    """
    验证 Public Key（public 接口使用）。

    默认不公开，需配置 public_key 才能访问；若开启 public_enabled 且未配置 public_key，则放开访问。
    管理端 app_key 始终可作为高级凭证访问 public 接口。
    """
    public_key = get_public_api_key()
    public_enabled = is_public_enabled()
    app_key = get_app_key()

    # 管理端凭证优先放行（用于后台复用 public 功能页）
    if auth and app_key and auth.credentials == app_key:
        return auth.credentials

    if not public_key:
        if public_enabled:
            return None
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Public access is disabled",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not auth:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if auth.credentials != public_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return auth.credentials
