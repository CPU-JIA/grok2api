"""
Grok Chat 服务
"""

import asyncio
import re
import uuid
from typing import Dict, List, Any, AsyncGenerator, AsyncIterable

import orjson
from curl_cffi.requests.errors import RequestsError

from app.core.logger import logger
from app.core.config import get_config
from app.core.exceptions import (
    AppException,
    ValidationException,
    ErrorType,
    UpstreamException,
    StreamIdleTimeoutError,
    StreamFirstTimeoutError,
    StreamTotalTimeoutError,
)
from app.services.grok.services.model import ModelService
from app.services.grok.utils.upload import UploadService
from app.services.grok.utils import process as proc_base
from app.services.grok.utils.retry import (
    pick_token,
    rate_limited,
    extract_status_code,
    rate_limit_has_quota,
)
from app.services.reverse.app_chat import AppChatReverse
from app.services.reverse.utils.session import ResettableSession
from app.services.grok.utils.stream import wrap_stream_with_usage
from app.services.token import get_token_manager, EffortType
from app.services.conversation_manager import conversation_manager


_CHAT_SEMAPHORE = None
_CHAT_SEM_VALUE = None


def extract_tool_text(raw: str, rollout_id: str = "") -> str:
    if not raw:
        return ""
    name_match = re.search(
        r"<xai:tool_name>(.*?)</xai:tool_name>", raw, flags=re.DOTALL
    )
    args_match = re.search(
        r"<xai:tool_args>(.*?)</xai:tool_args>", raw, flags=re.DOTALL
    )

    name = name_match.group(1) if name_match else ""
    if name:
        name = re.sub(r"<!\[CDATA\[(.*?)\]\]>", r"\1", name, flags=re.DOTALL).strip()

    args = args_match.group(1) if args_match else ""
    if args:
        args = re.sub(r"<!\[CDATA\[(.*?)\]\]>", r"\1", args, flags=re.DOTALL).strip()

    payload = None
    if args:
        try:
            payload = orjson.loads(args)
        except orjson.JSONDecodeError:
            payload = None

    label = name
    text = args
    prefix = f"[{rollout_id}]" if rollout_id else ""

    if name == "web_search":
        label = f"{prefix}[WebSearch]"
        if isinstance(payload, dict):
            text = payload.get("query") or payload.get("q") or ""
    elif name == "search_images":
        label = f"{prefix}[SearchImage]"
        if isinstance(payload, dict):
            text = (
                payload.get("image_description")
                or payload.get("description")
                or payload.get("query")
                or ""
            )
    elif name == "chatroom_send":
        label = f"{prefix}[AgentThink]"
        if isinstance(payload, dict):
            text = payload.get("message") or ""

    if label and text:
        return f"{label} {text}".strip()
    if label:
        return label
    if text:
        return text
    # Fallback: strip tags to keep any raw text.
    return re.sub(r"<[^>]+>", "", raw, flags=re.DOTALL).strip()


def _get_chat_semaphore() -> asyncio.Semaphore:
    global _CHAT_SEMAPHORE, _CHAT_SEM_VALUE
    value = max(1, int(get_config("chat.concurrent")))
    if value != _CHAT_SEM_VALUE:
        _CHAT_SEM_VALUE = value
        _CHAT_SEMAPHORE = asyncio.Semaphore(value)
    return _CHAT_SEMAPHORE


class MessageExtractor:
    """消息内容提取器"""

    @staticmethod
    def extract(
        messages: List[Dict[str, Any]],
        is_continue: bool = False,
    ) -> tuple[str, List[str], List[str]]:
        """从 OpenAI 消息格式提取内容，返回 (text, file_attachments, image_attachments)"""
        texts = []
        file_attachments: List[str] = []
        image_attachments: List[str] = []
        extracted = []

        for msg in messages:
            role = msg.get("role", "") or "user"
            content = msg.get("content", "")
            parts = []

            if isinstance(content, str):
                if content.strip():
                    parts.append(content)
            elif isinstance(content, list):
                for item in content:
                    item_type = item.get("type", "")

                    if item_type == "text":
                        if text := item.get("text", "").strip():
                            parts.append(text)

                    elif item_type == "image_url":
                        image_data = item.get("image_url", {})
                        url = image_data.get("url", "")
                        if url:
                            image_attachments.append(url)

                    elif item_type == "input_audio":
                        audio_data = item.get("input_audio", {})
                        data = audio_data.get("data", "")
                        if data:
                            file_attachments.append(data)

                    elif item_type == "file":
                        file_data = item.get("file", {})
                        raw = file_data.get("file_data", "")
                        if raw:
                            file_attachments.append(raw)

            if parts:
                extracted.append({"role": role, "text": "\n".join(parts)})

        if is_continue:
            # 继续对话：只发送最后一条 user 消息
            last_user = next(
                (m for m in reversed(messages) if m.get("role") == "user"), None
            )
            if not last_user and messages:
                last_user = messages[-1]
            if not last_user:
                return "", file_attachments, image_attachments

            role = last_user.get("role", "user")
            content = last_user.get("content", "")
            parts: List[str] = []

            if isinstance(content, str):
                if content.strip():
                    parts.append(content)
            elif isinstance(content, list):
                for item in content:
                    item_type = item.get("type", "")
                    if item_type == "text":
                        if text := item.get("text", "").strip():
                            parts.append(text)
                    elif item_type == "image_url":
                        image_data = item.get("image_url", {})
                        url = image_data.get("url", "")
                        if url:
                            image_attachments.append(url)
                    elif item_type == "input_audio":
                        audio_data = item.get("input_audio", {})
                        data = audio_data.get("data", "")
                        if data:
                            file_attachments.append(data)
                    elif item_type == "file":
                        file_data = item.get("file", {})
                        raw = file_data.get("file_data", "")
                        if raw:
                            file_attachments.append(raw)

            return (
                ("\n".join(parts) if parts else ""),
                file_attachments,
                image_attachments,
            )

        # 找到最后一条 user 消息
        last_user_index = next(
            (
                i
                for i in range(len(extracted) - 1, -1, -1)
                if extracted[i]["role"] == "user"
            ),
            None,
        )

        for i, item in enumerate(extracted):
            role = item["role"] or "user"
            text = item["text"]
            texts.append(text if i == last_user_index else f"{role}: {text}")

        return "\n\n".join(texts), file_attachments, image_attachments


class GrokChatService:
    """Grok API 调用服务"""

    async def chat(
        self,
        token: str,
        message: str,
        model: str,
        mode: str = None,
        stream: bool = None,
        file_attachments: List[str] = None,
        tool_overrides: Dict[str, Any] = None,
        model_config_override: Dict[str, Any] = None,
        conversation_id: str | None = None,
        parent_response_id: str | None = None,
    ):
        """发送聊天请求"""
        if stream is None:
            stream = get_config("app.stream")

        logger.debug(
            f"Chat request: model={model}, mode={mode}, stream={stream}, attachments={len(file_attachments or [])}"
        )

        browser = get_config("proxy.browser")

        async def _stream():
            session = ResettableSession(impersonate=browser)
            try:
                async with _get_chat_semaphore():
                    if conversation_id and parent_response_id:
                        stream_response = await AppChatReverse.request_continue(
                            session,
                            token,
                            conversation_id=conversation_id,
                            parent_response_id=parent_response_id,
                            message=message,
                            model=model,
                            mode=mode,
                            file_attachments=file_attachments,
                            tool_overrides=tool_overrides,
                            model_config_override=model_config_override,
                        )
                    else:
                        stream_response = await AppChatReverse.request(
                            session,
                            token,
                            message=message,
                            model=model,
                            mode=mode,
                            file_attachments=file_attachments,
                            tool_overrides=tool_overrides,
                            model_config_override=model_config_override,
                        )
                    logger.info(f"Chat connected: model={model}, stream={stream}")
                    async for line in stream_response:
                        yield line
            except Exception:
                try:
                    await session.close()
                except Exception:
                    pass
                raise

        return _stream()

    async def chat_openai(
        self,
        token: str,
        model: str,
        messages: List[Dict[str, Any]],
        stream: bool = None,
        reasoning_effort: str | None = None,
        temperature: float = 0.8,
        top_p: float = 0.95,
        conversation_id: str | None = None,
        parent_response_id: str | None = None,
        is_continue: bool = False,
    ):
        """OpenAI 兼容接口"""
        model_info = ModelService.get(model)
        if not model_info:
            raise ValidationException(f"Unknown model: {model}")

        grok_model = model_info.grok_model
        mode = model_info.model_mode
        # 提取消息和附件
        message, file_attachments, image_attachments = MessageExtractor.extract(
            messages, is_continue=is_continue
        )
        logger.debug(
            "Extracted message length=%s, files=%s, images=%s",
            len(message),
            len(file_attachments),
            len(image_attachments),
        )

        # 上传附件
        file_ids: List[str] = []
        image_ids: List[str] = []
        if file_attachments or image_attachments:
            upload_service = UploadService()
            try:
                for attach_data in file_attachments:
                    file_id, _ = await upload_service.upload_file(attach_data, token)
                    file_ids.append(file_id)
                    logger.debug(f"Attachment uploaded: type=file, file_id={file_id}")
                for attach_data in image_attachments:
                    file_id, _ = await upload_service.upload_file(attach_data, token)
                    image_ids.append(file_id)
                    logger.debug(f"Attachment uploaded: type=image, file_id={file_id}")
            finally:
                await upload_service.close()

        all_attachments = file_ids + image_ids
        stream = stream if stream is not None else get_config("app.stream")

        model_config_override = {
            "temperature": temperature,
            "topP": top_p,
        }
        if reasoning_effort is not None:
            model_config_override["reasoningEffort"] = reasoning_effort

        response = await self.chat(
            token,
            message,
            grok_model,
            mode,
            stream,
            file_attachments=all_attachments,
            model_config_override=model_config_override,
            conversation_id=conversation_id,
            parent_response_id=parent_response_id,
        )

        return response, stream, model


class ChatService:
    """Chat 业务服务"""

    @staticmethod
    async def completions(
        model: str,
        messages: List[Dict[str, Any]],
        stream: bool = None,
        reasoning_effort: str | None = None,
        temperature: float = 0.8,
        top_p: float = 0.95,
        conversation_id: str | None = None,
    ):
        """Chat Completions 入口"""
        # 获取 token
        token_mgr = await get_token_manager()
        await token_mgr.reload_if_stale()

        await conversation_manager.init()

        # 解析参数
        if reasoning_effort is None:
            show_think = get_config("app.thinking")
        else:
            show_think = reasoning_effort != "none"
        is_stream = stream if stream is not None else get_config("app.stream")

        openai_conv_id = conversation_id
        context = None
        if conversation_id:
            context = await conversation_manager.get_conversation(conversation_id)

        if not context and messages and len(messages) > 1:
            auto_conv_id = await conversation_manager.find_conversation_by_history(
                messages
            )
            if auto_conv_id:
                context = await conversation_manager.get_conversation(auto_conv_id)
                openai_conv_id = auto_conv_id

        if openai_conv_id is None:
            openai_conv_id = conversation_manager.generate_id()

        # 跨 Token 重试循环
        tried_tokens = set()
        max_token_retries = int(get_config("retry.max_retry"))
        last_error = None

        for attempt in range(max_token_retries):
            # 选择 token
            preferred = context.token if context else None
            token = await pick_token(
                token_mgr, model, tried_tokens, preferred=preferred
            )
            if not token:
                if last_error:
                    raise last_error
                raise AppException(
                    message="No available tokens. Please try again later.",
                    error_type=ErrorType.RATE_LIMIT.value,
                    code="rate_limit_exceeded",
                    status_code=429,
                )

            tried_tokens.add(token)

            try:
                # 若会话跨账号，尝试克隆分享会话
                if context and token != context.token:
                    if context.share_link_id:
                        (
                            new_conv_id,
                            new_resp_id,
                        ) = await AppChatReverse.clone_share_link(
                            token, context.share_link_id
                        )
                        if new_conv_id and new_resp_id:
                            await conversation_manager.update_conversation(
                                openai_conv_id,
                                new_resp_id,
                                share_link_id=context.share_link_id,
                                grok_conversation_id=new_conv_id,
                                token=token,
                                increment_message=False,
                            )
                            context = await conversation_manager.get_conversation(
                                openai_conv_id
                            )
                        else:
                            context = None
                    else:
                        context = None

                    if context is None:
                        openai_conv_id = conversation_manager.generate_id()

                # 请求 Grok
                service = GrokChatService()
                response, _, model_name = await service.chat_openai(
                    token,
                    model,
                    messages,
                    stream=is_stream,
                    reasoning_effort=reasoning_effort,
                    temperature=temperature,
                    top_p=top_p,
                    conversation_id=context.conversation_id if context else None,
                    parent_response_id=context.last_response_id if context else None,
                    is_continue=bool(context),
                )

                # 处理响应
                if is_stream:
                    logger.debug(f"Processing stream response: model={model}")
                    processor = StreamProcessor(
                        model_name, token, show_think, openai_conv_id
                    )

                    async def _update_conversation_from_processor():
                        grok_conv_id = processor.grok_conversation_id or (
                            context.conversation_id if context else ""
                        )
                        grok_resp_id = processor.response_id
                        if not grok_conv_id or not grok_resp_id:
                            return

                        if context:
                            await conversation_manager.update_conversation(
                                openai_conv_id,
                                grok_resp_id,
                                messages=messages,
                                grok_conversation_id=grok_conv_id,
                                token=token,
                            )
                        else:
                            await conversation_manager.create_conversation(
                                token,
                                grok_conv_id,
                                grok_resp_id,
                                messages=messages,
                                openai_conv_id=openai_conv_id,
                            )

                        async def _share():
                            share_link_id = await AppChatReverse.share_conversation(
                                token, grok_conv_id, grok_resp_id
                            )
                            if share_link_id:
                                await conversation_manager.update_conversation(
                                    openai_conv_id,
                                    grok_resp_id,
                                    share_link_id=share_link_id,
                                    grok_conversation_id=grok_conv_id,
                                    token=token,
                                    increment_message=False,
                                )

                        asyncio.create_task(_share())

                    async def stream_wrapper():
                        success = False
                        try:
                            async for chunk in wrap_stream_with_usage(
                                processor.process(response), token_mgr, token, model
                            ):
                                yield chunk
                            success = True
                        finally:
                            if success:
                                await _update_conversation_from_processor()

                    return stream_wrapper()

                # 非流式
                logger.debug(f"Processing non-stream response: model={model}")
                collector = CollectProcessor(model_name, token)
                result = await collector.process(response)
                try:
                    model_info = ModelService.get(model)
                    effort = (
                        EffortType.HIGH
                        if (model_info and model_info.cost.value == "high")
                        else EffortType.LOW
                    )
                    await token_mgr.consume(token, effort)
                    logger.info(f"Chat completed: model={model}, effort={effort.value}")
                except Exception as e:
                    logger.warning(f"Failed to record usage: {e}")

                grok_conv_id = collector.grok_conversation_id or (
                    context.conversation_id if context else ""
                )
                grok_resp_id = collector.response_id
                if grok_conv_id and grok_resp_id:
                    if context:
                        await conversation_manager.update_conversation(
                            openai_conv_id,
                            grok_resp_id,
                            messages=messages,
                            grok_conversation_id=grok_conv_id,
                            token=token,
                        )
                    else:
                        await conversation_manager.create_conversation(
                            token,
                            grok_conv_id,
                            grok_resp_id,
                            messages=messages,
                            openai_conv_id=openai_conv_id,
                        )

                    async def _share():
                        share_link_id = await AppChatReverse.share_conversation(
                            token, grok_conv_id, grok_resp_id
                        )
                        if share_link_id:
                            await conversation_manager.update_conversation(
                                openai_conv_id,
                                grok_resp_id,
                                share_link_id=share_link_id,
                                grok_conversation_id=grok_conv_id,
                                token=token,
                                increment_message=False,
                            )

                    asyncio.create_task(_share())

                result["conversation_id"] = openai_conv_id
                return result

            except UpstreamException as e:
                last_error = e

                if rate_limited(e):
                    has_quota = rate_limit_has_quota(e)
                    await token_mgr.apply_cooldown(
                        token,
                        429,
                        has_quota=has_quota,
                        reason="rate_limit",
                    )
                    logger.warning(
                        f"Token {token[:10]}... rate limited (429), "
                        f"trying next token (attempt {attempt + 1}/{max_token_retries})"
                    )
                    continue

                status = extract_status_code(e)
                if status and status not in (401, 403):
                    await token_mgr.apply_cooldown(
                        token,
                        int(status),
                        reason=f"status_{status}",
                    )
                    logger.warning(
                        f"Token {token[:10]}... status={status}, "
                        f"trying next token (attempt {attempt + 1}/{max_token_retries})"
                    )
                    continue

                raise

        # 所有 token 都 429，抛出最后的错误
        if last_error:
            raise last_error
        raise AppException(
            message="No available tokens. Please try again later.",
            error_type=ErrorType.RATE_LIMIT.value,
            code="rate_limit_exceeded",
            status_code=429,
        )


class StreamProcessor(proc_base.BaseProcessor):
    """Stream response processor."""

    def __init__(
        self,
        model: str,
        token: str = "",
        show_think: bool = None,
        conversation_id: str | None = None,
    ):
        super().__init__(model, token)
        self.response_id: str = None
        self.grok_conversation_id: str = ""
        self.conversation_id: str | None = conversation_id
        self.fingerprint: str = ""
        self.rollout_id: str = ""
        self.think_opened: bool = False
        self.image_think_active: bool = False
        self.role_sent: bool = False
        self.filter_tags = get_config("app.filter_tags")
        self.tool_usage_enabled = "xai:tool_usage_card" in (self.filter_tags or [])
        self._tool_usage_opened = False
        self._tool_usage_buffer = ""

        self.show_think = bool(show_think)

    def _filter_tool_card(self, token: str) -> str:
        if not token or not self.tool_usage_enabled:
            return token

        output_parts: list[str] = []
        rest = token
        start_tag = "<xai:tool_usage_card"
        end_tag = "</xai:tool_usage_card>"

        while rest:
            if self._tool_usage_opened:
                end_idx = rest.find(end_tag)
                if end_idx == -1:
                    self._tool_usage_buffer += rest
                    return "".join(output_parts)
                end_pos = end_idx + len(end_tag)
                self._tool_usage_buffer += rest[:end_pos]
                line = extract_tool_text(self._tool_usage_buffer, self.rollout_id)
                if line:
                    if output_parts and not output_parts[-1].endswith("\n"):
                        output_parts[-1] += "\n"
                    output_parts.append(f"{line}\n")
                self._tool_usage_buffer = ""
                self._tool_usage_opened = False
                rest = rest[end_pos:]
                continue

            start_idx = rest.find(start_tag)
            if start_idx == -1:
                output_parts.append(rest)
                break

            if start_idx > 0:
                output_parts.append(rest[:start_idx])

            end_idx = rest.find(end_tag, start_idx)
            if end_idx == -1:
                self._tool_usage_opened = True
                self._tool_usage_buffer = rest[start_idx:]
                break

            end_pos = end_idx + len(end_tag)
            raw_card = rest[start_idx:end_pos]
            line = extract_tool_text(raw_card, self.rollout_id)
            if line:
                if output_parts and not output_parts[-1].endswith("\n"):
                    output_parts[-1] += "\n"
                output_parts.append(f"{line}\n")
            rest = rest[end_pos:]

        return "".join(output_parts)

    def _filter_token(self, token: str) -> str:
        """Filter special tags in current token only."""
        if not token:
            return token

        if self.tool_usage_enabled:
            token = self._filter_tool_card(token)
            if not token:
                return ""

        if not self.filter_tags:
            return token

        for tag in self.filter_tags:
            if tag == "xai:tool_usage_card":
                continue
            if f"<{tag}" in token or f"</{tag}" in token:
                return ""

        return token

    def _sse(self, content: str = "", role: str = None, finish: str = None) -> str:
        """Build SSE response."""
        delta = {}
        if role:
            delta["role"] = role
            delta["content"] = ""
        elif content:
            delta["content"] = content

        chunk = {
            "id": self.response_id or f"chatcmpl-{uuid.uuid4().hex[:24]}",
            "object": "chat.completion.chunk",
            "created": self.created,
            "model": self.model,
            "system_fingerprint": self.fingerprint,
            "choices": [
                {"index": 0, "delta": delta, "logprobs": None, "finish_reason": finish}
            ],
        }
        if self.conversation_id:
            chunk["conversation_id"] = self.conversation_id
        return f"data: {orjson.dumps(chunk).decode()}\n\n"

    async def process(
        self, response: AsyncIterable[bytes]
    ) -> AsyncGenerator[str, None]:
        """Process stream response.

        Args:
            response: AsyncIterable[bytes], async iterable of bytes

        Returns:
            AsyncGenerator[str, None], async generator of strings
        """
        idle_timeout = get_config("chat.stream_timeout")
        first_timeout = get_config("chat.stream_first_timeout", 0)
        total_timeout = get_config("chat.stream_total_timeout", 0)

        try:
            async for line in proc_base._with_stream_timeouts(
                response,
                first_timeout=first_timeout,
                idle_timeout=idle_timeout,
                total_timeout=total_timeout,
                model=self.model,
            ):
                line = proc_base._normalize_line(line)
                if not line:
                    continue
                try:
                    data = orjson.loads(line)
                except orjson.JSONDecodeError:
                    continue

                resp = data.get("result", {}).get("response", {})
                is_thinking = bool(resp.get("isThinking"))
                # isThinking controls <think> tagging
                # when absent, treat as False

                if (llm := resp.get("llmInfo")) and not self.fingerprint:
                    self.fingerprint = llm.get("modelHash", "")
                if rid := resp.get("responseId"):
                    self.response_id = rid
                if mr := resp.get("modelResponse"):
                    if rid := mr.get("responseId"):
                        self.response_id = rid
                if rid := resp.get("rolloutId"):
                    self.rollout_id = str(rid)
                if conv := data.get("result", {}).get("conversation"):
                    if conv_id := conv.get("conversationId"):
                        self.grok_conversation_id = conv_id

                if not self.role_sent:
                    yield self._sse(role="assistant")
                    self.role_sent = True

                if img := resp.get("streamingImageGenerationResponse"):
                    if not self.show_think:
                        continue
                    self.image_think_active = True
                    if not self.think_opened:
                        yield self._sse("<think>\n")
                        self.think_opened = True
                    idx = img.get("imageIndex", 0) + 1
                    progress = img.get("progress", 0)
                    yield self._sse(f"正在生成第{idx}张图片中，当前进度{progress}%\n")
                    continue

                if mr := resp.get("modelResponse"):
                    if self.image_think_active and self.think_opened:
                        yield self._sse("\n</think>\n")
                        self.think_opened = False
                    self.image_think_active = False
                    for url in proc_base._collect_images(mr):
                        parts = url.split("/")
                        img_id = parts[-2] if len(parts) >= 2 else "image"
                        dl_service = self._get_dl()
                        rendered = await dl_service.render_image(
                            url, self.token, img_id
                        )
                        yield self._sse(f"{rendered}\n")

                    if (
                        (meta := mr.get("metadata", {}))
                        .get("llm_info", {})
                        .get("modelHash")
                    ):
                        self.fingerprint = meta["llm_info"]["modelHash"]
                    continue

                if card := resp.get("cardAttachment"):
                    json_data = card.get("jsonData")
                    if isinstance(json_data, str) and json_data.strip():
                        try:
                            card_data = orjson.loads(json_data)
                        except orjson.JSONDecodeError:
                            card_data = None
                        if isinstance(card_data, dict):
                            image = card_data.get("image") or {}
                            original = image.get("original")
                            title = image.get("title") or ""
                            if original:
                                title_safe = title.replace("\n", " ").strip()
                                if title_safe:
                                    yield self._sse(f"![{title_safe}]({original})\n")
                                else:
                                    yield self._sse(f"![image]({original})\n")
                    continue

                if (token := resp.get("token")) is not None:
                    if not token:
                        continue
                    filtered = self._filter_token(token)
                    if not filtered:
                        continue
                    in_think = is_thinking or self.image_think_active
                    if in_think:
                        if not self.show_think:
                            continue
                        if not self.think_opened:
                            yield self._sse("<think>\n")
                            self.think_opened = True
                    else:
                        if self.think_opened:
                            yield self._sse("\n</think>\n")
                            self.think_opened = False
                    yield self._sse(filtered)

            if self.think_opened:
                yield self._sse("</think>\n")
            yield self._sse(finish="stop")
            yield "data: [DONE]\n\n"
        except asyncio.CancelledError:
            logger.debug("Stream cancelled by client", extra={"model": self.model})
        except StreamFirstTimeoutError as e:
            raise UpstreamException(
                message=f"Stream first response timeout after {e.first_seconds}s",
                status_code=504,
                details={
                    "error": str(e),
                    "type": "stream_first_timeout",
                    "first_seconds": e.first_seconds,
                },
            )
        except StreamTotalTimeoutError as e:
            raise UpstreamException(
                message=f"Stream total timeout after {e.total_seconds}s",
                status_code=504,
                details={
                    "error": str(e),
                    "type": "stream_total_timeout",
                    "total_seconds": e.total_seconds,
                },
            )
        except StreamIdleTimeoutError as e:
            raise UpstreamException(
                message=f"Stream idle timeout after {e.idle_seconds}s",
                status_code=504,
                details={
                    "error": str(e),
                    "type": "stream_idle_timeout",
                    "idle_seconds": e.idle_seconds,
                },
            )
        except RequestsError as e:
            if proc_base._is_http2_error(e):
                logger.warning(f"HTTP/2 stream error: {e}", extra={"model": self.model})
                raise UpstreamException(
                    message="Upstream connection closed unexpectedly",
                    status_code=502,
                    details={"error": str(e), "type": "http2_stream_error"},
                )
            logger.error(f"Stream request error: {e}", extra={"model": self.model})
            raise UpstreamException(
                message=f"Upstream request failed: {e}",
                status_code=502,
                details={"error": str(e)},
            )
        except Exception as e:
            logger.error(
                f"Stream processing error: {e}",
                extra={"model": self.model, "error_type": type(e).__name__},
            )
            raise
        finally:
            await self.close()


class CollectProcessor(proc_base.BaseProcessor):
    """Non-stream response processor."""

    def __init__(self, model: str, token: str = ""):
        super().__init__(model, token)
        self.filter_tags = get_config("app.filter_tags")
        self.response_id: str = ""
        self.grok_conversation_id: str = ""

    def _filter_content(self, content: str) -> str:
        """Filter special tags in content."""
        if not content or not self.filter_tags:
            return content

        result = content
        if "xai:tool_usage_card" in self.filter_tags:
            rollout_id = ""
            rollout_match = re.search(
                r"<rolloutId>(.*?)</rolloutId>", result, flags=re.DOTALL
            )
            if rollout_match:
                rollout_id = rollout_match.group(1).strip()

            result = re.sub(
                r"<xai:tool_usage_card[^>]*>.*?</xai:tool_usage_card>",
                lambda match: (
                    f"{extract_tool_text(match.group(0), rollout_id)}\n"
                    if extract_tool_text(match.group(0), rollout_id)
                    else ""
                ),
                result,
                flags=re.DOTALL,
            )

        for tag in self.filter_tags:
            if tag == "xai:tool_usage_card":
                continue
            pattern = rf"<{re.escape(tag)}[^>]*>.*?</{re.escape(tag)}>|<{re.escape(tag)}[^>]*/>"
            result = re.sub(pattern, "", result, flags=re.DOTALL)

        return result

    async def process(self, response: AsyncIterable[bytes]) -> dict[str, Any]:
        """Process and collect full response."""
        response_id = ""
        fingerprint = ""
        content = ""
        idle_timeout = get_config("chat.stream_timeout")
        first_timeout = get_config("chat.stream_first_timeout", 0)
        total_timeout = get_config("chat.stream_total_timeout", 0)

        try:
            async for line in proc_base._with_stream_timeouts(
                response,
                first_timeout=first_timeout,
                idle_timeout=idle_timeout,
                total_timeout=total_timeout,
                model=self.model,
            ):
                line = proc_base._normalize_line(line)
                if not line:
                    continue
                try:
                    data = orjson.loads(line)
                except orjson.JSONDecodeError:
                    continue

                result_root = data.get("result", {}) or {}
                resp = result_root.get("response", {}) or {}

                if conv := result_root.get("conversation"):
                    if conv_id := conv.get("conversationId"):
                        self.grok_conversation_id = conv_id

                if (llm := resp.get("llmInfo")) and not fingerprint:
                    fingerprint = llm.get("modelHash", "")

                if mr := resp.get("modelResponse"):
                    response_id = mr.get("responseId", "") or response_id
                    content = mr.get("message", "")

                    card_map: dict[str, tuple[str, str]] = {}
                    for raw in mr.get("cardAttachmentsJson") or []:
                        if not isinstance(raw, str) or not raw.strip():
                            continue
                        try:
                            card_data = orjson.loads(raw)
                        except orjson.JSONDecodeError:
                            continue
                        if not isinstance(card_data, dict):
                            continue
                        card_id = card_data.get("id")
                        image = card_data.get("image") or {}
                        original = image.get("original")
                        if not card_id or not original:
                            continue
                        title = image.get("title") or ""
                        card_map[card_id] = (title, original)

                    if content and card_map:

                        def _render_card(match: re.Match) -> str:
                            card_id = match.group(1)
                            item = card_map.get(card_id)
                            if not item:
                                return ""
                            title, original = item
                            title_safe = title.replace("\n", " ").strip() or "image"
                            prefix = ""
                            if match.start() > 0:
                                prev = content[match.start() - 1]
                                if prev not in ("\n", "\r"):
                                    prefix = "\n"
                            return f"{prefix}![{title_safe}]({original})"

                        content = re.sub(
                            r'<grok:render[^>]*card_id="([^"]+)"[^>]*>.*?</grok:render>',
                            _render_card,
                            content,
                            flags=re.DOTALL,
                        )

                    if urls := proc_base._collect_images(mr):
                        content += "\n"
                        for url in urls:
                            parts = url.split("/")
                            img_id = parts[-2] if len(parts) >= 2 else "image"
                            dl_service = self._get_dl()
                            rendered = await dl_service.render_image(
                                url, self.token, img_id
                            )
                            content += f"{rendered}\n"

                    if (
                        (meta := mr.get("metadata", {}))
                        .get("llm_info", {})
                        .get("modelHash")
                    ):
                        fingerprint = meta["llm_info"]["modelHash"]

        except asyncio.CancelledError:
            logger.debug("Collect cancelled by client", extra={"model": self.model})
        except StreamFirstTimeoutError as e:
            logger.warning(
                f"Collect first response timeout: {e}", extra={"model": self.model}
            )
        except StreamTotalTimeoutError as e:
            logger.warning(f"Collect total timeout: {e}", extra={"model": self.model})
        except StreamIdleTimeoutError as e:
            logger.warning(f"Collect idle timeout: {e}", extra={"model": self.model})
        except RequestsError as e:
            if proc_base._is_http2_error(e):
                logger.warning(
                    f"HTTP/2 stream error in collect: {e}", extra={"model": self.model}
                )
            else:
                logger.error(f"Collect request error: {e}", extra={"model": self.model})
        except Exception as e:
            logger.error(
                f"Collect processing error: {e}",
                extra={"model": self.model, "error_type": type(e).__name__},
            )
        finally:
            await self.close()

        content = self._filter_content(content)
        self.response_id = response_id

        return {
            "id": response_id,
            "object": "chat.completion",
            "created": self.created,
            "model": self.model,
            "system_fingerprint": fingerprint,
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": content,
                        "refusal": None,
                        "annotations": [],
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
                "prompt_tokens_details": {
                    "cached_tokens": 0,
                    "text_tokens": 0,
                    "audio_tokens": 0,
                    "image_tokens": 0,
                },
                "completion_tokens_details": {
                    "text_tokens": 0,
                    "audio_tokens": 0,
                    "reasoning_tokens": 0,
                },
            },
        }


__all__ = [
    "GrokChatService",
    "MessageExtractor",
    "ChatService",
]
