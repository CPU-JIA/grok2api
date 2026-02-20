"""
MCP tool implementations.
"""

from __future__ import annotations

from typing import Any, Optional

from app.core.logger import logger
from app.services.grok.services.chat import ChatService
from app.services.grok.services.model import ModelService


def _flatten_message_content(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                text = item.get("text") if item.get("type") == "text" else ""
                if isinstance(text, str) and text:
                    parts.append(text)
        return "".join(parts)
    return str(content)


async def ask_grok_impl(
    query: str,
    model: str = "grok-3-fast",
    system_prompt: Optional[str] = None,
) -> str:
    """Call Grok through existing chat pipeline and return plain text reply."""
    prompt = (query or "").strip()
    if not prompt:
        raise ValueError("query cannot be empty")

    chosen_model = (model or "").strip() or "grok-3-fast"
    if not ModelService.valid(chosen_model):
        raise ValueError(f"invalid model: {chosen_model}")

    messages = []
    if system_prompt and str(system_prompt).strip():
        messages.append({"role": "system", "content": str(system_prompt).strip()})
    messages.append({"role": "user", "content": prompt})

    logger.info(f"[MCP] ask_grok request model={chosen_model}")

    result = await ChatService.completions(
        model=chosen_model,
        messages=messages,
        stream=False,
        reasoning_effort=None,
    )

    if not isinstance(result, dict):
        raise RuntimeError("unexpected streaming response from ChatService")

    choices = result.get("choices") or []
    if not choices:
        return ""

    message = choices[0].get("message") or {}
    content = _flatten_message_content(message.get("content"))
    logger.info(f"[MCP] ask_grok completed chars={len(content)}")
    return content


__all__ = ["ask_grok_impl"]
