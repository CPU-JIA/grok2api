from fastapi import APIRouter, Depends, Query

from app.core.auth import verify_app_key
from app.services.request_stats import request_stats

router = APIRouter()


@router.get("/stats", dependencies=[Depends(verify_app_key)])
async def get_stats(
    hours: int = Query(24, ge=1, le=168),
    days: int = Query(7, ge=1, le=90),
):
    return request_stats.get_stats(hours=hours, days=days)


__all__ = ["router"]
