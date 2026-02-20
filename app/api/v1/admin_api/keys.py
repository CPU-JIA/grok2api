from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.core.auth import verify_app_key
from app.services.api_keys import api_key_manager

router = APIRouter()


class KeyCreateRequest(BaseModel):
    name: str = ""
    count: int = Field(1, ge=1, le=100)


class KeyUpdateRequest(BaseModel):
    key: str = Field(..., min_length=1)
    name: Optional[str] = None
    is_active: Optional[bool] = None


class KeyDeleteRequest(BaseModel):
    keys: List[str] = Field(..., min_length=1)


@router.get("/keys", dependencies=[Depends(verify_app_key)])
async def list_keys():
    await api_key_manager.init()
    items = []
    for item in api_key_manager.list_keys():
        key = item.get("key", "")
        items.append(
            {
                "key": key,
                "masked_key": api_key_manager.mask_key(key),
                "name": item.get("name", ""),
                "created_at": item.get("created_at"),
                "is_active": item.get("is_active", True),
                "usage_count": item.get("usage_count", 0),
                "last_used_at": item.get("last_used_at"),
            }
        )
    return {"keys": items, "stats": api_key_manager.get_stats()}


@router.post("/keys", dependencies=[Depends(verify_app_key)])
async def create_keys(payload: KeyCreateRequest):
    await api_key_manager.init()
    if payload.count > 1:
        keys = await api_key_manager.batch_add_keys(payload.name, payload.count)
        return {"created": keys}
    key = await api_key_manager.add_key(payload.name)
    return {"created": [key]}


@router.patch("/keys", dependencies=[Depends(verify_app_key)])
async def update_key(payload: KeyUpdateRequest):
    ok = await api_key_manager.update_key(payload.key, payload.name, payload.is_active)
    if not ok:
        raise HTTPException(status_code=404, detail="Key not found")
    return {"ok": True}


@router.delete("/keys", dependencies=[Depends(verify_app_key)])
async def delete_keys(payload: KeyDeleteRequest):
    deleted = await api_key_manager.delete_keys(payload.keys)
    return {"deleted": deleted}


__all__ = ["router"]
