import asyncio
import time
import uuid
from typing import Optional, List, Dict, Any

import orjson
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    Request,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.core.auth import has_public_access, verify_public_key
from app.core.config import get_config
from app.core.logger import logger
from app.services.request_logger import request_logger
from app.services.request_stats import request_stats
from app.api.v1.image import resolve_aspect_ratio, resolve_response_format
from app.services.grok.services.image import ImageGenerationService
from app.services.grok.services.model import ModelService
from app.services.token.manager import get_token_manager

router = APIRouter()

IMAGINE_SESSION_TTL = 600
IMAGINE_DEFAULT_COUNT = 6
IMAGINE_MAX_COUNT = 16
IMAGINE_STREAM_MAX = 6
_IMAGINE_SESSIONS: dict[str, dict] = {}
_IMAGINE_SESSIONS_LOCK = asyncio.Lock()


async def _clean_sessions(now: float) -> None:
    expired = [
        key
        for key, info in _IMAGINE_SESSIONS.items()
        if now - float(info.get("created_at") or 0) > IMAGINE_SESSION_TTL
    ]
    for key in expired:
        _IMAGINE_SESSIONS.pop(key, None)


def _parse_sse_chunk(chunk: str) -> Optional[Dict[str, Any]]:
    if not chunk:
        return None
    event = None
    data_lines: List[str] = []
    for raw in str(chunk).splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("event:"):
            event = line[6:].strip()
            continue
        if line.startswith("data:"):
            data_lines.append(line[5:].strip())
    if not data_lines:
        return None
    data_str = "\n".join(data_lines)
    if data_str == "[DONE]":
        return None
    try:
        payload = orjson.loads(data_str)
    except orjson.JSONDecodeError:
        return None
    if event and isinstance(payload, dict) and "type" not in payload:
        payload["type"] = event
    return payload


def _normalize_count(value: Optional[int]) -> int:
    if value is None:
        return IMAGINE_DEFAULT_COUNT
    try:
        count = int(value)
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=400,
            detail=f"n must be an integer between 1 and {IMAGINE_MAX_COUNT}",
        )
    if count < 1 or count > IMAGINE_MAX_COUNT:
        raise HTTPException(
            status_code=400,
            detail=f"n must be between 1 and {IMAGINE_MAX_COUNT}",
        )
    return count


def _normalize_response_format(value: Optional[str]) -> str:
    if value is None or str(value).strip() == "":
        fmt = resolve_response_format(None)
    else:
        fmt = resolve_response_format(str(value).strip().lower())
    if fmt == "base64":
        fmt = "b64_json"
    return fmt


def _public_query_key_allowed(
    key: Optional[str], cookies: Optional[Dict[str, str]] = None
) -> bool:
    return has_public_access((key or "").strip(), cookies)


def _get_client_ip(req: Request) -> str:
    for header in ("x-forwarded-for", "x-real-ip", "cf-connecting-ip"):
        value = req.headers.get(header)
        if value:
            return value.split(",")[0].strip()
    if req.client:
        return req.client.host or ""
    return ""


def _extract_status_code(exc: Exception, default: int = 500) -> int:
    status = getattr(exc, "status_code", None)
    details = getattr(exc, "details", None)
    if status is None and isinstance(details, dict):
        status = details.get("status")
    try:
        return int(status or default)
    except Exception:
        return default


async def _new_session(
    prompt: str,
    aspect_ratio: str,
    nsfw: Optional[bool],
    n: int,
    response_format: str,
) -> str:
    task_id = uuid.uuid4().hex
    now = time.time()
    async with _IMAGINE_SESSIONS_LOCK:
        await _clean_sessions(now)
        _IMAGINE_SESSIONS[task_id] = {
            "prompt": prompt,
            "aspect_ratio": aspect_ratio,
            "nsfw": nsfw,
            "n": n,
            "response_format": response_format,
            "created_at": now,
        }
    return task_id


async def _get_session(task_id: str) -> Optional[dict]:
    if not task_id:
        return None
    now = time.time()
    async with _IMAGINE_SESSIONS_LOCK:
        await _clean_sessions(now)
        info = _IMAGINE_SESSIONS.get(task_id)
        if not info:
            return None
        created_at = float(info.get("created_at") or 0)
        if now - created_at > IMAGINE_SESSION_TTL:
            _IMAGINE_SESSIONS.pop(task_id, None)
            return None
        return dict(info)


async def _drop_session(task_id: str) -> None:
    if not task_id:
        return
    async with _IMAGINE_SESSIONS_LOCK:
        _IMAGINE_SESSIONS.pop(task_id, None)


async def _drop_sessions(task_ids: List[str]) -> int:
    if not task_ids:
        return 0
    removed = 0
    async with _IMAGINE_SESSIONS_LOCK:
        for task_id in task_ids:
            if task_id and task_id in _IMAGINE_SESSIONS:
                _IMAGINE_SESSIONS.pop(task_id, None)
                removed += 1
    return removed


@router.websocket("/imagine/ws")
async def public_imagine_ws(websocket: WebSocket):
    session_id = None
    session_info = None
    task_id = websocket.query_params.get("task_id")
    if task_id:
        info = await _get_session(task_id)
        if info:
            session_id = task_id
            session_info = info

    ok = True
    if session_id is None:
        key = websocket.query_params.get("public_key")
        ok = _public_query_key_allowed(key, websocket.cookies)

    if not ok:
        await websocket.close(code=1008)
        return

    await websocket.accept()
    stop_event = asyncio.Event()
    run_task: Optional[asyncio.Task] = None

    async def _send(payload: dict) -> bool:
        try:
            await websocket.send_text(orjson.dumps(payload).decode())
            return True
        except Exception:
            return False

    async def _stop_run():
        nonlocal run_task
        stop_event.set()
        if run_task and not run_task.done():
            run_task.cancel()
            try:
                await run_task
            except Exception:
                pass
        run_task = None
        stop_event.clear()

    async def _run(
        prompt: str,
        aspect_ratio: str,
        nsfw: Optional[bool],
        n: int,
        response_format: str,
    ):
        model_id = "grok-imagine-1.0"
        model_info = ModelService.get(model_id)
        if not model_info or not model_info.is_image:
            await _send(
                {
                    "type": "error",
                    "message": "Image model is not available.",
                    "code": "model_not_supported",
                }
            )
            return

        token_mgr = await get_token_manager()
        run_id = uuid.uuid4().hex

        await _send(
            {
                "type": "status",
                "status": "running",
                "prompt": prompt,
                "aspect_ratio": aspect_ratio,
                "run_id": run_id,
            }
        )

        response_field = "url" if response_format == "url" else "b64_json"
        sequence = 0

        while not stop_event.is_set():
            try:
                await token_mgr.reload_if_stale()
                token = None
                for pool_name in ModelService.pool_candidates_for_model(
                    model_info.model_id
                ):
                    token = token_mgr.get_token(pool_name)
                    if token:
                        break

                if not token:
                    await _send(
                        {
                            "type": "error",
                            "message": "No available tokens. Please try again later.",
                            "code": "rate_limit_exceeded",
                        }
                    )
                    await asyncio.sleep(2)
                    continue

                stream_enabled = n <= IMAGINE_STREAM_MAX
                result = await ImageGenerationService().generate(
                    token_mgr=token_mgr,
                    token=token,
                    model_info=model_info,
                    prompt=prompt,
                    n=n,
                    response_format=response_format,
                    size="1024x1024",
                    aspect_ratio=aspect_ratio,
                    stream=stream_enabled,
                    enable_nsfw=nsfw,
                )
                if result.stream:
                    async for chunk in result.data:
                        payload = _parse_sse_chunk(chunk)
                        if not payload:
                            continue
                        if isinstance(payload, dict):
                            payload.setdefault("run_id", run_id)
                        await _send(payload)
                else:
                    images = [img for img in result.data if img and img != "error"]
                    if images:
                        for img_b64 in images:
                            sequence += 1
                            await _send(
                                {
                                    "type": "image",
                                    response_field: img_b64,
                                    "sequence": sequence,
                                    "created_at": int(time.time() * 1000),
                                    "aspect_ratio": aspect_ratio,
                                    "run_id": run_id,
                                }
                            )
                    else:
                        await _send(
                            {
                                "type": "error",
                                "message": "Image generation returned empty data.",
                                "code": "empty_image",
                            }
                        )

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning(f"Imagine stream error: {e}")
                await _send(
                    {
                        "type": "error",
                        "message": str(e),
                        "code": "internal_error",
                    }
                )
                await asyncio.sleep(1.5)

        await _send({"type": "status", "status": "stopped", "run_id": run_id})

    try:
        while True:
            try:
                raw = await websocket.receive_text()
            except (RuntimeError, WebSocketDisconnect):
                break

            try:
                payload = orjson.loads(raw)
            except Exception:
                await _send(
                    {
                        "type": "error",
                        "message": "Invalid message format.",
                        "code": "invalid_payload",
                    }
                )
                continue

            action = payload.get("type")
            if action == "start":
                prompt = str(payload.get("prompt") or "").strip()
                if not prompt:
                    await _send(
                        {
                            "type": "error",
                            "message": "Prompt cannot be empty.",
                            "code": "invalid_prompt",
                        }
                    )
                    continue
                raw_ratio = payload.get("aspect_ratio")
                if raw_ratio is None and session_info:
                    raw_ratio = session_info.get("aspect_ratio")
                aspect_ratio = resolve_aspect_ratio(
                    str(raw_ratio or "2:3").strip() or "2:3"
                )
                nsfw = payload.get("nsfw")
                if nsfw is None and session_info:
                    nsfw = session_info.get("nsfw")
                if nsfw is not None:
                    nsfw = bool(nsfw)
                raw_n = payload.get("n")
                if raw_n is None and session_info:
                    raw_n = session_info.get("n")
                try:
                    count = _normalize_count(raw_n)
                except HTTPException as e:
                    await _send(
                        {
                            "type": "error",
                            "message": str(e.detail),
                            "code": "invalid_n",
                        }
                    )
                    continue

                raw_format = payload.get("response_format")
                if raw_format is None and session_info:
                    raw_format = session_info.get("response_format")
                try:
                    response_format = _normalize_response_format(raw_format)
                except Exception as e:
                    message = getattr(e, "detail", None) or str(e)
                    await _send(
                        {
                            "type": "error",
                            "message": message or "Invalid response_format",
                            "code": "invalid_response_format",
                        }
                    )
                    continue
                await _stop_run()
                run_task = asyncio.create_task(
                    _run(prompt, aspect_ratio, nsfw, count, response_format)
                )
            elif action == "stop":
                await _stop_run()
            else:
                await _send(
                    {
                        "type": "error",
                        "message": "Unknown action.",
                        "code": "invalid_action",
                    }
                )

    except WebSocketDisconnect:
        logger.debug("WebSocket disconnected by client")
    except Exception as e:
        logger.warning(f"WebSocket error: {e}")
    finally:
        await _stop_run()

        try:
            from starlette.websockets import WebSocketState

            if websocket.client_state == WebSocketState.CONNECTED:
                await websocket.close(code=1000, reason="Server closing connection")
        except Exception as e:
            logger.debug(f"WebSocket close ignored: {e}")
        if session_id:
            await _drop_session(session_id)


@router.get("/imagine/sse")
async def public_imagine_sse(
    request: Request,
    task_id: str = Query(""),
    prompt: str = Query(""),
    aspect_ratio: str = Query("2:3"),
    n: Optional[int] = Query(None),
    response_format: Optional[str] = Query(None),
):
    """Imagine 图片瀑布流（SSE 兜底）"""
    session = None
    if task_id:
        session = await _get_session(task_id)
        if not session:
            raise HTTPException(status_code=404, detail="Task not found")
    else:
        key = request.query_params.get("public_key")
        if not _public_query_key_allowed(key, request.cookies):
            raise HTTPException(status_code=401, detail="Invalid authentication token")

    if session:
        prompt = str(session.get("prompt") or "").strip()
        ratio = str(session.get("aspect_ratio") or "2:3").strip() or "2:3"
        nsfw = session.get("nsfw")
        count = _normalize_count(session.get("n"))
        response_format = _normalize_response_format(session.get("response_format"))
    else:
        prompt = (prompt or "").strip()
        if not prompt:
            raise HTTPException(status_code=400, detail="Prompt cannot be empty")
        ratio = str(aspect_ratio or "2:3").strip() or "2:3"
        ratio = resolve_aspect_ratio(ratio)
        nsfw = request.query_params.get("nsfw")
        if nsfw is not None:
            nsfw = str(nsfw).lower() in ("1", "true", "yes", "on")
        count = _normalize_count(n)
        response_format = _normalize_response_format(response_format)

    start_time = time.time()
    client_ip = _get_client_ip(request)
    model_id = "grok-imagine-1.0"

    async def record(success: bool, status: int, error: str = "", stream: bool = True):
        duration_ms = int((time.time() - start_time) * 1000)
        try:
            await request_stats.record(model_id, success=success)
            await request_logger.log(
                model=model_id,
                status=status,
                duration_ms=duration_ms,
                ip=client_ip,
                key_name="Public",
                key_masked="",
                error=error,
                stream=stream,
            )
        except Exception:
            pass

    async def event_stream():
        ok = False
        status = 200
        err = ""
        try:
            model_info = ModelService.get(model_id)
            if not model_info or not model_info.is_image:
                status = 503
                err = "Image model is not available."
                yield (
                    f"data: {orjson.dumps({'type': 'error', 'message': err, 'code': 'model_not_supported'}).decode()}\n\n"
                )
                return

            token_mgr = await get_token_manager()
            sequence = 0
            run_id = uuid.uuid4().hex
            response_field = "url" if response_format == "url" else "b64_json"

            yield (
                f"data: {orjson.dumps({'type': 'status', 'status': 'running', 'prompt': prompt, 'aspect_ratio': ratio, 'run_id': run_id}).decode()}\n\n"
            )

            while True:
                if await request.is_disconnected():
                    break
                if task_id:
                    session_alive = await _get_session(task_id)
                    if not session_alive:
                        break

                try:
                    await token_mgr.reload_if_stale()
                    token = None
                    for pool_name in ModelService.pool_candidates_for_model(
                        model_info.model_id
                    ):
                        token = token_mgr.get_token(pool_name)
                        if token:
                            break

                    if not token:
                        status = 429
                        err = "No available tokens. Please try again later."
                        yield (
                            f"data: {orjson.dumps({'type': 'error', 'message': err, 'code': 'rate_limit_exceeded'}).decode()}\n\n"
                        )
                        await asyncio.sleep(2)
                        continue

                    stream_enabled = count <= IMAGINE_STREAM_MAX
                    result = await ImageGenerationService().generate(
                        token_mgr=token_mgr,
                        token=token,
                        model_info=model_info,
                        prompt=prompt,
                        n=count,
                        response_format=response_format,
                        size="1024x1024",
                        aspect_ratio=ratio,
                        stream=stream_enabled,
                        enable_nsfw=nsfw,
                    )
                    if result.stream:
                        async for chunk in result.data:
                            payload = _parse_sse_chunk(chunk)
                            if not payload:
                                continue
                            if isinstance(payload, dict):
                                payload.setdefault("run_id", run_id)
                            yield f"data: {orjson.dumps(payload).decode()}\n\n"
                    else:
                        images = [img for img in result.data if img and img != "error"]
                        if images:
                            for img_b64 in images:
                                sequence += 1
                                payload = {
                                    "type": "image",
                                    response_field: img_b64,
                                    "sequence": sequence,
                                    "created_at": int(time.time() * 1000),
                                    "aspect_ratio": ratio,
                                    "run_id": run_id,
                                }
                                yield f"data: {orjson.dumps(payload).decode()}\n\n"
                        else:
                            status = 502
                            err = "Image generation returned empty data."
                            yield (
                                f"data: {orjson.dumps({'type': 'error', 'message': err, 'code': 'empty_image'}).decode()}\n\n"
                            )
                except asyncio.CancelledError:
                    break
                except Exception as exc:
                    status = _extract_status_code(exc)
                    err = str(exc)
                    logger.warning(f"Imagine SSE error: {exc}")
                    yield (
                        f"data: {orjson.dumps({'type': 'error', 'message': err, 'code': 'internal_error'}).decode()}\n\n"
                    )
                    await asyncio.sleep(1.5)

            ok = True
            yield (
                f"data: {orjson.dumps({'type': 'status', 'status': 'stopped', 'run_id': run_id}).decode()}\n\n"
            )
        finally:
            await record(ok, status if ok else status or 500, error=err, stream=True)
            if task_id:
                await _drop_session(task_id)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


@router.get("/imagine/config")
async def public_imagine_config():
    return {
        "final_min_bytes": int(get_config("image.final_min_bytes") or 0),
        "medium_min_bytes": int(get_config("image.medium_min_bytes") or 0),
        "nsfw": bool(get_config("image.nsfw")),
    }


class ImagineStartRequest(BaseModel):
    prompt: str
    aspect_ratio: Optional[str] = "2:3"
    nsfw: Optional[bool] = None
    n: Optional[int] = None
    response_format: Optional[str] = None


@router.post("/imagine/start", dependencies=[Depends(verify_public_key)])
async def public_imagine_start(request: Request, data: ImagineStartRequest):
    start_time = time.time()
    client_ip = _get_client_ip(request)
    model_id = "grok-imagine-1.0"

    async def record(success: bool, status: int, error: str = ""):
        duration_ms = int((time.time() - start_time) * 1000)
        try:
            await request_stats.record(model_id, success=success)
            await request_logger.log(
                model=model_id,
                status=status,
                duration_ms=duration_ms,
                ip=client_ip,
                key_name="Public",
                key_masked="",
                error=error,
                stream=False,
            )
        except Exception:
            pass

    try:
        prompt = (data.prompt or "").strip()
        if not prompt:
            raise HTTPException(status_code=400, detail="Prompt cannot be empty")
        ratio = resolve_aspect_ratio(str(data.aspect_ratio or "2:3").strip() or "2:3")
        count = _normalize_count(data.n)
        response_format = _normalize_response_format(data.response_format)
        task_id = await _new_session(prompt, ratio, data.nsfw, count, response_format)
        await record(True, 200)
        return {
            "task_id": task_id,
            "aspect_ratio": ratio,
            "n": count,
            "response_format": response_format,
        }
    except Exception as exc:
        await record(False, _extract_status_code(exc), error=str(exc))
        raise


class ImagineStopRequest(BaseModel):
    task_ids: List[str]


@router.post("/imagine/stop", dependencies=[Depends(verify_public_key)])
async def public_imagine_stop(request: Request, data: ImagineStopRequest):
    start_time = time.time()
    client_ip = _get_client_ip(request)
    model_id = "grok-imagine-1.0"

    async def record(success: bool, status: int, error: str = ""):
        duration_ms = int((time.time() - start_time) * 1000)
        try:
            await request_stats.record(model_id, success=success)
            await request_logger.log(
                model=model_id,
                status=status,
                duration_ms=duration_ms,
                ip=client_ip,
                key_name="Public",
                key_masked="",
                error=error,
                stream=False,
            )
        except Exception:
            pass

    try:
        removed = await _drop_sessions(data.task_ids or [])
        await record(True, 200)
        return {"status": "success", "removed": removed}
    except Exception as exc:
        await record(False, _extract_status_code(exc), error=str(exc))
        raise
