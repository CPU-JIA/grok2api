import time
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel

from app.core.auth import (
    clear_public_session_cookie,
    has_public_access,
    set_public_session_cookie,
    verify_public_key,
)
from app.core.exceptions import AppException
from app.services.grok.services.voice import VoiceService
from app.services.token.manager import get_token_manager
from app.services.request_logger import request_logger
from app.services.request_stats import request_stats

router = APIRouter()


class VoiceTokenResponse(BaseModel):
    token: str
    url: str
    participant_name: str = ""
    room_name: str = ""


class PublicSessionLoginRequest(BaseModel):
    key: str = ""


@router.get(
    "/voice/token",
    dependencies=[Depends(verify_public_key)],
    response_model=VoiceTokenResponse,
)
async def public_voice_token(
    raw_request: Request,
    voice: str = "ara",
    personality: str = "assistant",
    speed: float = 1.0,
):
    """获取 Grok Voice Mode (LiveKit) Token"""
    start_time = time.time()
    model_id = "grok-voice-livekit"

    def client_ip() -> str:
        for header in ("x-forwarded-for", "x-real-ip", "cf-connecting-ip"):
            value = raw_request.headers.get(header)
            if value:
                return value.split(",")[0].strip()
        if raw_request.client:
            return raw_request.client.host or ""
        return ""

    async def record(success: bool, status: int, error: str = ""):
        duration_ms = int((time.time() - start_time) * 1000)
        try:
            await request_stats.record(model_id, success=success)
            await request_logger.log(
                model=model_id,
                status=status,
                duration_ms=duration_ms,
                ip=client_ip(),
                key_name="Public",
                key_masked="",
                error=error,
                stream=False,
            )
        except Exception:
            pass

    token_mgr = await get_token_manager()
    sso_token = None
    for pool_name in ("ssoBasic", "ssoSuper"):
        sso_token = token_mgr.get_token(pool_name)
        if sso_token:
            break

    if not sso_token:
        err = AppException(
            "No available tokens for voice mode",
            code="no_token",
            status_code=503,
        )
        await record(False, err.status_code, error=str(err))
        raise err

    service = VoiceService()
    try:
        data = await service.get_token(
            token=sso_token,
            voice=voice,
            personality=personality,
            speed=speed,
        )
        token = data.get("token")
        if not token:
            raise AppException(
                "Upstream returned no voice token",
                code="upstream_error",
                status_code=502,
            )

        await record(True, 200)
        return VoiceTokenResponse(
            token=token,
            url="wss://livekit.grok.com",
            participant_name="",
            room_name="",
        )

    except Exception as e:
        if isinstance(e, AppException):
            await record(False, e.status_code, error=str(e))
            raise
        await record(False, 500, error=str(e))
        raise AppException(
            f"Voice token error: {str(e)}",
            code="voice_error",
            status_code=500,
        )


@router.post("/session")
async def public_create_session(
    payload: PublicSessionLoginRequest, request: Request, response: Response
):
    if not has_public_access(payload.key, request.cookies):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
        )

    set_public_session_cookie(response, request)
    return {"status": "success"}


@router.delete("/session")
async def public_delete_session(response: Response):
    clear_public_session_cookie(response)
    return {"status": "success"}


@router.get("/verify", dependencies=[Depends(verify_public_key)])
async def public_verify_api():
    """验证 Public Key"""
    return {"status": "success"}
