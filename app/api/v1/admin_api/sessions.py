import time

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.core.auth import verify_app_key
from app.core.config import get_config
from app.services.conversation_manager import conversation_manager

router = APIRouter()


class ConversationDeleteRequest(BaseModel):
    conversation_id: str = Field(..., min_length=1)


@router.get("/sessions", dependencies=[Depends(verify_app_key)])
async def list_sessions():
    await conversation_manager.init()
    ttl = int(get_config("conversation.ttl_seconds", 24 * 3600))
    now = time.time()

    conversations = []
    for conv_id, ctx in conversation_manager.conversations.items():
        ttl_remaining = max(0, int(ttl - (now - ctx.updated_at)))
        token = ctx.token
        masked_token = token
        if masked_token and len(masked_token) > 12:
            masked_token = f"{masked_token[:12]}..."

        hash_status = "none"
        if ctx.history_hash:
            mapped = conversation_manager.hash_to_conversation.get(ctx.history_hash)
            hash_status = "matched" if mapped == conv_id else "stale"

        conversations.append(
            {
                "conversation_id": conv_id,
                "grok_conversation_id": ctx.conversation_id,
                "last_response_id": ctx.last_response_id,
                "share_link_id": ctx.share_link_id,
                "history_hash": ctx.history_hash,
                "hash_status": hash_status,
                "token": masked_token,
                "message_count": ctx.message_count,
                "created_at": ctx.created_at,
                "last_active": ctx.updated_at,
                "ttl_remaining": ttl_remaining,
            }
        )

    conversations.sort(key=lambda x: x.get("last_active", 0), reverse=True)
    return {"conversations": conversations, "stats": conversation_manager.get_stats()}


@router.delete("/sessions", dependencies=[Depends(verify_app_key)])
async def delete_session(payload: ConversationDeleteRequest):
    await conversation_manager.init()
    if payload.conversation_id not in conversation_manager.conversations:
        raise HTTPException(status_code=404, detail="Conversation not found")
    await conversation_manager.delete_conversation(payload.conversation_id)
    return {"ok": True}


@router.post("/sessions/clear", dependencies=[Depends(verify_app_key)])
async def clear_sessions():
    await conversation_manager.clear()
    return {"ok": True}


__all__ = ["router"]
