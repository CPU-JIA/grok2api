"""
Reverse interface: app chat conversations.
"""

import orjson
from typing import Any, Dict, List, Optional
from curl_cffi.requests import AsyncSession

from app.core.logger import logger
from app.core.config import get_config
from app.core.exceptions import UpstreamException
from app.services.token.service import TokenService
from app.services.reverse.utils.headers import build_headers
from app.services.reverse.utils.retry import retry_on_status
from app.services.proxy_pool import (
    request_with_proxy_retry,
    get_proxy_url,
    build_proxies,
)

CHAT_API = "https://grok.com/rest/app-chat/conversations/new"
CHAT_CONTINUE_API = (
    "https://grok.com/rest/app-chat/conversations/{conversation_id}/responses"
)
CHAT_SHARE_API = "https://grok.com/rest/app-chat/conversations/{conversation_id}/share"
CHAT_CLONE_API = "https://grok.com/rest/app-chat/share_links/{share_link_id}/clone"


class AppChatReverse:
    """/rest/app-chat/conversations/new reverse interface."""

    @staticmethod
    def build_payload(
        message: str,
        model: str,
        mode: str = None,
        file_attachments: List[str] = None,
        tool_overrides: Dict[str, Any] = None,
        model_config_override: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """Build chat payload for Grok app-chat API."""

        attachments = file_attachments or []

        payload = {
            "deviceEnvInfo": {
                "darkModeEnabled": False,
                "devicePixelRatio": 2,
                "screenWidth": 2056,
                "screenHeight": 1329,
                "viewportWidth": 2056,
                "viewportHeight": 1083,
            },
            "disableMemory": get_config("app.disable_memory"),
            "disableSearch": False,
            "disableSelfHarmShortCircuit": False,
            "disableTextFollowUps": False,
            "enableImageGeneration": True,
            "enableImageStreaming": True,
            "enableSideBySide": True,
            "fileAttachments": attachments,
            "forceConcise": False,
            "forceSideBySide": False,
            "imageAttachments": [],
            "imageGenerationCount": 2,
            "isAsyncChat": False,
            "isReasoning": False,
            "message": message,
            "modelMode": mode,
            "modelName": model,
            "responseMetadata": {
                "requestModelDetails": {"modelId": model},
            },
            "returnImageBytes": False,
            "returnRawGrokInXaiRequest": False,
            "sendFinalMetadata": True,
            "temporary": get_config("app.temporary"),
            "toolOverrides": tool_overrides or {},
        }

        if model_config_override:
            payload["responseMetadata"]["modelConfigOverride"] = model_config_override

        return payload

    @staticmethod
    def build_continue_payload(
        message: str,
        model: str,
        mode: str,
        parent_response_id: str,
        file_attachments: List[str] = None,
        tool_overrides: Dict[str, Any] = None,
        model_config_override: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        payload = AppChatReverse.build_payload(
            message=message,
            model=model,
            mode=mode,
            file_attachments=file_attachments,
            tool_overrides=tool_overrides,
            model_config_override=model_config_override,
        )
        payload["parentResponseId"] = parent_response_id
        return payload

    @staticmethod
    async def request(
        session: AsyncSession,
        token: str,
        message: str,
        model: str,
        mode: str = None,
        file_attachments: List[str] = None,
        tool_overrides: Dict[str, Any] = None,
        model_config_override: Dict[str, Any] = None,
    ) -> Any:
        """Send app chat request to Grok.

        Args:
            session: AsyncSession, the session to use for the request.
            token: str, the SSO token.
            message: str, the message to send.
            model: str, the model to use.
            mode: str, the mode to use.
            file_attachments: List[str], the file attachments to send.
            tool_overrides: Dict[str, Any], the tool overrides to use.
            model_config_override: Dict[str, Any], the model config override to use.

        Returns:
            Any: The response from the request.
        """
        try:
            # Build headers
            headers = build_headers(
                cookie_token=token,
                content_type="application/json",
                origin="https://grok.com",
                referer="https://grok.com/",
            )

            # Build payload
            payload = AppChatReverse.build_payload(
                message=message,
                model=model,
                mode=mode,
                file_attachments=file_attachments,
                tool_overrides=tool_overrides,
                model_config_override=model_config_override,
            )

            # Curl Config
            timeout = max(
                float(get_config("chat.timeout") or 0),
                float(get_config("video.timeout") or 0),
                float(get_config("image.timeout") or 0),
            )
            browser = get_config("proxy.browser")

            async def _do_request(proxy_url, proxies, attempt):
                response = await session.post(
                    CHAT_API,
                    headers=headers,
                    data=orjson.dumps(payload),
                    timeout=timeout,
                    stream=True,
                    proxies=proxies,
                    impersonate=browser,
                )

                return response

            async def _send_request():
                response = await request_with_proxy_retry(_do_request)
                if response.status_code != 200:
                    content = ""
                    try:
                        content = await response.text()
                    except Exception:
                        pass

                    logger.error(
                        f"AppChatReverse: Chat failed, {response.status_code}",
                        extra={"error_type": "UpstreamException"},
                    )
                    raise UpstreamException(
                        message=f"AppChatReverse: Chat failed, {response.status_code}",
                        details={"status": response.status_code, "body": content},
                    )
                return response

            def extract_status(e: Exception) -> Optional[int]:
                if isinstance(e, UpstreamException):
                    if e.details and "status" in e.details:
                        status = e.details["status"]
                    else:
                        status = getattr(e, "status_code", None)
                    if status == 429:
                        return None
                    return status
                return None

            response = await retry_on_status(
                _send_request, extract_status=extract_status
            )

            # Stream response
            async def stream_response():
                try:
                    async for line in response.aiter_lines():
                        yield line
                finally:
                    await session.close()

            return stream_response()

        except Exception as e:
            # Handle upstream exception
            if isinstance(e, UpstreamException):
                status = None
                if e.details and "status" in e.details:
                    status = e.details["status"]
                else:
                    status = getattr(e, "status_code", None)
                if status == 401:
                    try:
                        await TokenService.record_fail(
                            token, status, "app_chat_auth_failed"
                        )
                    except Exception:
                        pass
                raise

            # Handle other non-upstream exceptions
            logger.error(
                f"AppChatReverse: Chat failed, {str(e)}",
                extra={"error_type": type(e).__name__},
            )
            raise UpstreamException(
                message=f"AppChatReverse: Chat failed, {str(e)}",
                details={"status": 502, "error": str(e)},
            )

    @staticmethod
    async def request_continue(
        session: AsyncSession,
        token: str,
        conversation_id: str,
        parent_response_id: str,
        message: str,
        model: str,
        mode: str = None,
        file_attachments: List[str] = None,
        tool_overrides: Dict[str, Any] = None,
        model_config_override: Dict[str, Any] = None,
    ) -> Any:
        """Send app chat continue request to Grok."""
        try:
            headers = build_headers(
                cookie_token=token,
                content_type="application/json",
                origin="https://grok.com",
                referer="https://grok.com/",
            )

            payload = AppChatReverse.build_continue_payload(
                message=message,
                model=model,
                mode=mode,
                parent_response_id=parent_response_id,
                file_attachments=file_attachments,
                tool_overrides=tool_overrides,
                model_config_override=model_config_override,
            )

            timeout = max(
                float(get_config("chat.timeout") or 0),
                float(get_config("video.timeout") or 0),
                float(get_config("image.timeout") or 0),
            )
            browser = get_config("proxy.browser")

            async def _do_request(proxy_url, proxies, attempt):
                response = await session.post(
                    CHAT_CONTINUE_API.format(conversation_id=conversation_id),
                    headers=headers,
                    data=orjson.dumps(payload),
                    timeout=timeout,
                    stream=True,
                    proxies=proxies,
                    impersonate=browser,
                )
                return response

            async def _send_request():
                response = await request_with_proxy_retry(_do_request)
                if response.status_code != 200:
                    content = ""
                    try:
                        content = await response.text()
                    except Exception:
                        pass
                    logger.error(
                        f"AppChatReverse: Continue failed, {response.status_code}",
                        extra={"error_type": "UpstreamException"},
                    )
                    raise UpstreamException(
                        message=f"AppChatReverse: Continue failed, {response.status_code}",
                        details={"status": response.status_code, "body": content},
                    )
                return response

            def extract_status(e: Exception) -> Optional[int]:
                if isinstance(e, UpstreamException):
                    if e.details and "status" in e.details:
                        status = e.details["status"]
                    else:
                        status = getattr(e, "status_code", None)
                    if status == 429:
                        return None
                    return status
                return None

            response = await retry_on_status(
                _send_request, extract_status=extract_status
            )

            async def stream_response():
                try:
                    async for line in response.aiter_lines():
                        yield line
                finally:
                    await session.close()

            return stream_response()

        except Exception as e:
            if isinstance(e, UpstreamException):
                status = None
                if e.details and "status" in e.details:
                    status = e.details["status"]
                else:
                    status = getattr(e, "status_code", None)
                if status == 401:
                    try:
                        await TokenService.record_fail(
                            token, status, "app_chat_continue_auth_failed"
                        )
                    except Exception:
                        pass
                raise

            logger.error(
                f"AppChatReverse: Continue failed, {str(e)}",
                extra={"error_type": type(e).__name__},
            )
            raise UpstreamException(
                message=f"AppChatReverse: Continue failed, {str(e)}",
                details={"status": 502, "error": str(e)},
            )

    @staticmethod
    async def share_conversation(
        token: str,
        conversation_id: str,
        response_id: str,
    ) -> Optional[str]:
        if not conversation_id or not response_id:
            return None
        headers = build_headers(
            cookie_token=token,
            content_type="application/json",
            origin="https://grok.com",
            referer="https://grok.com/",
        )
        payload = {"responseId": response_id, "allowIndexing": True}
        try:
            async with AsyncSession(impersonate=get_config("proxy.browser")) as session:
                proxy_url = await get_proxy_url()
                proxies = build_proxies(proxy_url)
                response = await session.post(
                    CHAT_SHARE_API.format(conversation_id=conversation_id),
                    headers=headers,
                    data=orjson.dumps(payload),
                    timeout=30,
                    proxies=proxies,
                )
                if response.status_code != 200:
                    return None
                data = orjson.loads(response.content)
                return data.get("shareLinkId")
        except Exception:
            return None

    @staticmethod
    async def clone_share_link(
        token: str,
        share_link_id: str,
    ) -> tuple[Optional[str], Optional[str]]:
        if not share_link_id:
            return None, None
        headers = build_headers(
            cookie_token=token,
            content_type="application/json",
            origin="https://grok.com",
            referer="https://grok.com/",
        )
        try:
            async with AsyncSession(impersonate=get_config("proxy.browser")) as session:
                proxy_url = await get_proxy_url()
                proxies = build_proxies(proxy_url)
                response = await session.post(
                    CHAT_CLONE_API.format(share_link_id=share_link_id),
                    headers=headers,
                    data=orjson.dumps({}),
                    timeout=30,
                    proxies=proxies,
                )
                if response.status_code != 200:
                    return None, None
                data = orjson.loads(response.content)
                new_conv_id = data.get("conversation", {}).get("conversationId")
                if not new_conv_id:
                    return None, None
                responses = data.get("responses", []) or []
                last_resp_id = None
                for resp in reversed(responses):
                    if resp.get("sender") == "assistant":
                        last_resp_id = resp.get("responseId")
                        break
                if not last_resp_id and responses:
                    last_resp_id = responses[-1].get("responseId")
                return new_conv_id, last_resp_id
        except Exception:
            return None, None


__all__ = ["AppChatReverse"]
