import os

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel

from app.core.auth import (
    clear_admin_session_cookie,
    clear_public_session_cookie,
    get_app_key,
    is_valid_app_key,
    set_admin_session_cookie,
    verify_app_key,
)
from app.core.config import config
from app.core.storage import (
    LocalStorage,
    RedisStorage,
    SQLStorage,
    get_storage as get_storage_instance,
)

router = APIRouter()


class SessionLoginRequest(BaseModel):
    key: str = ""


@router.post("/session")
async def admin_create_session(
    payload: SessionLoginRequest, request: Request, response: Response
):
    if not get_app_key():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="App key is not configured",
        )

    if not is_valid_app_key(payload.key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
        )

    set_admin_session_cookie(response, request)
    return {"status": "success"}


@router.delete("/session")
async def admin_delete_session(response: Response):
    clear_admin_session_cookie(response)
    # Keep behavior explicit: admin logout should also clear public web session.
    clear_public_session_cookie(response)
    return {"status": "success"}


@router.get("/verify", dependencies=[Depends(verify_app_key)])
async def admin_verify():
    """Verify admin access."""
    return {"status": "success"}


@router.get("/config", dependencies=[Depends(verify_app_key)])
async def get_config():
    """Get current runtime config."""
    return config._config


@router.post("/config", dependencies=[Depends(verify_app_key)])
async def update_config(data: dict):
    """Update runtime config."""
    try:
        await config.update(data)
        return {"status": "success", "message": "配置已更新"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/storage", dependencies=[Depends(verify_app_key)])
async def get_storage_type():
    """Get active storage backend name."""
    storage_type = os.getenv("SERVER_STORAGE_TYPE", "").lower()
    if not storage_type:
        storage = get_storage_instance()
        if isinstance(storage, LocalStorage):
            storage_type = "local"
        elif isinstance(storage, RedisStorage):
            storage_type = "redis"
        elif isinstance(storage, SQLStorage):
            storage_type = {
                "mysql": "mysql",
                "mariadb": "mysql",
                "postgres": "pgsql",
                "postgresql": "pgsql",
                "pgsql": "pgsql",
            }.get(storage.dialect, storage.dialect)
    return {"type": storage_type or "local"}
