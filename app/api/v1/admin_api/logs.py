from fastapi import APIRouter, Depends, Query

from app.core.auth import verify_app_key
from app.services.request_logger import request_logger

router = APIRouter()


@router.get("/logs", dependencies=[Depends(verify_app_key)])
async def get_logs(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    return await request_logger.list_logs(limit=limit, offset=offset)


@router.post("/logs/clear", dependencies=[Depends(verify_app_key)])
async def clear_logs():
    await request_logger.clear()
    return {"ok": True}


__all__ = ["router"]
