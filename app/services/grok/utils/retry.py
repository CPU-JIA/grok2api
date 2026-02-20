"""
Retry helpers for token switching.
"""

from typing import Optional, Set

import orjson

from app.core.exceptions import UpstreamException
from app.services.grok.services.model import ModelService


async def pick_token(
    token_mgr,
    model_id: str,
    tried: Set[str],
    preferred: Optional[str] = None,
) -> Optional[str]:
    if preferred and preferred not in tried:
        try:
            if token_mgr.get_pool_name_for_token(preferred):
                return preferred
        except Exception:
            pass

    token = None
    for pool_name in ModelService.pool_candidates_for_model(model_id):
        token = token_mgr.get_token(pool_name, exclude=tried)
        if token:
            break

    if not token and not tried:
        result = await token_mgr.refresh_cooling_tokens()
        if result.get("recovered", 0) > 0:
            for pool_name in ModelService.pool_candidates_for_model(model_id):
                token = token_mgr.get_token(pool_name)
                if token:
                    break

    return token


def extract_status_code(error: Exception) -> Optional[int]:
    if isinstance(error, UpstreamException):
        if error.details and "status" in error.details:
            return error.details.get("status")
        return getattr(error, "status_code", None)
    return getattr(error, "status_code", None)


def rate_limit_has_quota(error: Exception) -> Optional[bool]:
    if not isinstance(error, UpstreamException):
        return None

    details = error.details or {}

    remaining = details.get("remainingTokens")
    if remaining is None:
        remaining = details.get("remainingQueries")
    if isinstance(remaining, (int, float)):
        return remaining > 0 or remaining == -1

    body = details.get("body")
    if not body:
        return None

    if isinstance(body, bytes):
        try:
            body = body.decode("utf-8", errors="ignore")
        except Exception:
            return None

    if isinstance(body, str):
        try:
            payload = orjson.loads(body)
        except Exception:
            return None
    elif isinstance(body, dict):
        payload = body
    else:
        return None

    for key in ("remainingTokens", "remainingQueries"):
        value = payload.get(key)
        if isinstance(value, (int, float)):
            return value > 0 or value == -1

    return None


def rate_limited(error: Exception) -> bool:
    if not isinstance(error, UpstreamException):
        return False
    status = extract_status_code(error)
    code = error.details.get("error_code") if error.details else None
    return status == 429 or code == "rate_limit_exceeded"


__all__ = [
    "pick_token",
    "rate_limited",
    "extract_status_code",
    "rate_limit_has_quota",
]
