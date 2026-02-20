"""会话管理器 - 多轮对话上下文管理"""

import asyncio
import hashlib
import time
import uuid
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional

from app.core.config import get_config
from app.core.logger import logger
from app.core.storage import get_storage


DEFAULT_SAVE_DELAY_MS = 500


@dataclass
class ConversationContext:
    conversation_id: str  # Grok 会话 ID
    last_response_id: str  # 最后一条响应 ID
    created_at: float
    updated_at: float
    message_count: int
    token: str
    history_hash: str = ""
    share_link_id: str = ""


class ConversationManager:
    """管理真实上下文的多轮对话"""

    def __init__(self):
        self.conversations: Dict[str, ConversationContext] = {}
        self.token_conversations: Dict[str, List[str]] = {}
        self.hash_to_conversation: Dict[str, str] = {}
        self.initialized = False
        self._cleanup_task: Optional[asyncio.Task] = None
        self._last_cleanup_time: float = 0
        self._total_cleaned: int = 0
        self._save_lock = asyncio.Lock()
        self._dirty = False
        self._save_task: Optional[asyncio.Task] = None
        self._save_delay = DEFAULT_SAVE_DELAY_MS / 1000.0

    def _get_ttl(self) -> int:
        return int(get_config("conversation.ttl_seconds", 24 * 3600))

    def _get_cleanup_interval(self) -> int:
        return int(get_config("conversation.cleanup_interval_sec", 600))

    def _get_max_per_token(self) -> int:
        return int(get_config("conversation.max_per_token", 50))

    def _get_save_delay_sec(self) -> float:
        raw = get_config("conversation.save_delay_ms", DEFAULT_SAVE_DELAY_MS)
        try:
            delay_ms = float(raw)
        except Exception:
            delay_ms = float(DEFAULT_SAVE_DELAY_MS)
        return max(0.0, delay_ms / 1000.0)

    @staticmethod
    def compute_history_hash(messages: List[Dict[str, Any]], exclude_last_user: bool = False) -> str:
        if not messages:
            return ""

        system_parts: List[str] = []
        user_parts: List[str] = []
        has_assistant = False

        for msg in messages:
            role = msg.get("role", "")
            content = msg.get("content", "")

            if role == "system":
                if isinstance(content, list):
                    text_parts = [
                        item.get("text", "")
                        for item in content
                        if item.get("type") == "text"
                    ]
                    content = "".join(text_parts)
                system_parts.append(f"system:{content}")
            elif role == "user":
                if isinstance(content, list):
                    text_parts = [
                        item.get("text", "")
                        for item in content
                        if item.get("type") == "text"
                    ]
                    content = "".join(text_parts)
                user_parts.append(f"user:{content}")
            elif role == "assistant":
                has_assistant = True

        if exclude_last_user and has_assistant and user_parts:
            user_parts = user_parts[:-1]

        key_parts = system_parts + user_parts
        if not key_parts:
            return ""
        hash_input = "\n".join(key_parts).encode("utf-8")
        return hashlib.sha256(hash_input).hexdigest()[:16]

    async def init(self):
        if self.initialized:
            return
        storage = get_storage()
        data = await storage.load_json("conversations.json", {})

        for conv_id, conv_data in (data or {}).get("conversations", {}).items():
            if "history_hash" not in conv_data:
                conv_data["history_hash"] = ""
            if "share_link_id" not in conv_data:
                conv_data["share_link_id"] = ""
            context = ConversationContext(**conv_data)
            self.conversations[conv_id] = context
            if context.history_hash:
                self.hash_to_conversation[context.history_hash] = conv_id

        self.token_conversations = (data or {}).get("token_conversations", {})
        await self._cleanup_expired(persist=True)
        self._start_cleanup_task()
        self.initialized = True
        logger.info(f"ConversationManager loaded: {len(self.conversations)} sessions")

    def generate_id(self) -> str:
        return f"conv-{uuid.uuid4().hex[:24]}"

    async def find_conversation_by_history(self, messages: List[Dict[str, Any]]) -> Optional[str]:
        if not messages:
            return None
        history_hash = self.compute_history_hash(messages, exclude_last_user=True)
        if not history_hash:
            return None
        conv_id = self.hash_to_conversation.get(history_hash)
        if conv_id:
            context = await self.get_conversation(conv_id)
            if context:
                logger.info(f"[ConversationManager] Auto matched: {conv_id}, hash={history_hash}")
                return conv_id
            self.hash_to_conversation.pop(history_hash, None)
        return None

    async def create_conversation(
        self,
        token: str,
        grok_conversation_id: str,
        grok_response_id: str,
        messages: List[Dict[str, Any]] = None,
        share_link_id: str = "",
        openai_conv_id: Optional[str] = None,
    ) -> str:
        if openai_conv_id is None:
            openai_conv_id = self.generate_id()

        history_hash = ""
        if messages:
            history_hash = self.compute_history_hash(messages)

        context = ConversationContext(
            conversation_id=grok_conversation_id,
            last_response_id=grok_response_id,
            created_at=time.time(),
            updated_at=time.time(),
            message_count=1,
            token=token,
            history_hash=history_hash,
            share_link_id=share_link_id or "",
        )

        self.conversations[openai_conv_id] = context
        if history_hash:
            self.hash_to_conversation[history_hash] = openai_conv_id

        if token not in self.token_conversations:
            self.token_conversations[token] = []
        self.token_conversations[token].append(openai_conv_id)

        await self._limit_token_conversations(token)
        self._schedule_save()
        return openai_conv_id

    async def get_conversation(self, openai_conv_id: str) -> Optional[ConversationContext]:
        context = self.conversations.get(openai_conv_id)
        if context:
            if time.time() - context.updated_at > self._get_ttl():
                await self.delete_conversation(openai_conv_id)
                return None
        return context

    async def update_conversation(
        self,
        openai_conv_id: str,
        grok_response_id: str,
        messages: List[Dict[str, Any]] = None,
        share_link_id: Optional[str] = None,
        grok_conversation_id: Optional[str] = None,
        token: Optional[str] = None,
        increment_message: bool = True,
    ):
        context = self.conversations.get(openai_conv_id)
        if not context:
            return
        context.last_response_id = grok_response_id or context.last_response_id
        context.updated_at = time.time()
        if increment_message:
            context.message_count += 1

        if share_link_id is not None:
            context.share_link_id = share_link_id
        if grok_conversation_id is not None:
            context.conversation_id = grok_conversation_id
        if token is not None:
            context.token = token

        if messages:
            new_hash = self.compute_history_hash(messages)
            if new_hash and new_hash != context.history_hash:
                if context.history_hash:
                    self.hash_to_conversation.pop(context.history_hash, None)
                context.history_hash = new_hash
                self.hash_to_conversation[new_hash] = openai_conv_id

        self._schedule_save()

    async def delete_conversation(self, openai_conv_id: str, *, persist: bool = True) -> bool:
        context = self.conversations.pop(openai_conv_id, None)
        if not context:
            return False
        if context.history_hash:
            self.hash_to_conversation.pop(context.history_hash, None)
        if context.token in self.token_conversations:
            try:
                self.token_conversations[context.token].remove(openai_conv_id)
            except ValueError:
                pass
        if persist:
            self._schedule_save()
        return True

    async def clear(self):
        self.conversations.clear()
        self.token_conversations.clear()
        self.hash_to_conversation.clear()
        self._schedule_save()

    async def _limit_token_conversations(self, token: str):
        conv_ids = self.token_conversations.get(token, [])
        limit = self._get_max_per_token()
        if len(conv_ids) <= limit:
            return

        to_delete = len(conv_ids) - limit
        for conv_id in conv_ids[:to_delete]:
            ctx = self.conversations.pop(conv_id, None)
            if ctx and ctx.history_hash:
                self.hash_to_conversation.pop(ctx.history_hash, None)

        self.token_conversations[token] = conv_ids[to_delete:]

    async def _cleanup_expired(self, *, persist: bool = False) -> int:
        now = time.time()
        ttl = self._get_ttl()
        expired = [cid for cid, ctx in self.conversations.items() if now - ctx.updated_at > ttl]
        for cid in expired:
            await self.delete_conversation(cid, persist=False)
        if expired:
            self._total_cleaned += len(expired)
            if persist:
                self._schedule_save()
        self._last_cleanup_time = now
        return len(expired)

    def _start_cleanup_task(self):
        if self._cleanup_task is not None:
            return

        async def cleanup_loop():
            while True:
                try:
                    await asyncio.sleep(self._get_cleanup_interval())
                    await self._cleanup_expired(persist=True)
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"Conversation cleanup error: {e}")

        self._cleanup_task = asyncio.create_task(cleanup_loop())

    async def _stop_cleanup_task(self):
        task = self._cleanup_task
        if task is None:
            return
        self._cleanup_task = None
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.warning(f"Conversation cleanup task stop error: {e}")

    async def _save_async(self):
        async with self._save_lock:
            storage = get_storage()
            data = {
                "conversations": {
                    conv_id: asdict(ctx) for conv_id, ctx in self.conversations.items()
                },
                "token_conversations": self.token_conversations,
            }
            await storage.save_json("conversations.json", data)

    def _schedule_save(self):
        self._save_delay = self._get_save_delay_sec()
        self._dirty = True

        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return

        if self._save_delay == 0:
            if self._save_task and not self._save_task.done():
                return
            self._save_task = asyncio.create_task(self._save_async())
            return

        if self._save_task and not self._save_task.done():
            return
        self._save_task = asyncio.create_task(self._flush_loop())

    async def _flush_loop(self):
        try:
            while True:
                await asyncio.sleep(self._save_delay)
                if not self._dirty:
                    break
                self._dirty = False
                await self._save_async()
        finally:
            self._save_task = None
            if self._dirty:
                self._schedule_save()

    async def flush(self):
        task = self._save_task
        if task and not task.done():
            try:
                await task
            except Exception:
                pass
        if self._dirty:
            self._dirty = False
            await self._save_async()

    async def shutdown(self):
        await self._stop_cleanup_task()
        await self.flush()

    def get_stats(self) -> dict:
        total = len(self.conversations)
        avg_messages = (
            sum(c.message_count for c in self.conversations.values()) / total
            if total
            else 0
        )
        return {
            "total_conversations": total,
            "tokens_with_conversations": len(self.token_conversations),
            "avg_messages_per_conversation": avg_messages,
            "ttl_seconds": self._get_ttl(),
            "last_cleanup_time": self._last_cleanup_time,
            "total_cleaned": self._total_cleaned,
            "auto_cleanup_enabled": self._cleanup_task is not None,
        }


conversation_manager = ConversationManager()

__all__ = ["conversation_manager", "ConversationManager", "ConversationContext"]
