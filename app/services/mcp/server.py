"""
FastMCP server bootstrap.
"""

from __future__ import annotations

from typing import Any, Optional

from app.core.config import get_config
from app.core.logger import logger
from app.services.mcp.tools import ask_grok_impl

try:
    from fastmcp import FastMCP
except Exception:  # pragma: no cover - optional dependency
    FastMCP = None  # type: ignore[assignment]

try:
    from fastmcp.server.auth.providers.jwt import StaticTokenVerifier
except Exception:  # pragma: no cover - optional dependency
    StaticTokenVerifier = None  # type: ignore[assignment]


def _build_auth() -> Optional[Any]:
    if StaticTokenVerifier is None:
        return None

    token = str(get_config("mcp.api_key") or get_config("app.api_key") or "").strip()
    if not token:
        return None

    try:
        return StaticTokenVerifier(
            tokens={
                token: {
                    "client_id": "grok2api-client",
                    "scopes": ["read", "write"],
                }
            },
            required_scopes=["read"],
        )
    except Exception as e:
        logger.warning(f"Failed to create MCP auth verifier: {e}")
        return None


def create_mcp_server() -> Optional[Any]:
    if FastMCP is None:
        logger.warning("FastMCP not installed; MCP endpoint disabled")
        return None

    try:
        return FastMCP(
            name="grok2api-mcp",
            instructions="Use ask_grok to query Grok models with full context support.",
            auth=_build_auth(),
        )
    except TypeError:
        # Compatibility fallback for older/newer FastMCP constructors.
        return FastMCP(
            name="grok2api-mcp",
            instructions="Use ask_grok to query Grok models with full context support.",
        )


mcp = create_mcp_server()


if mcp is not None:

    @mcp.tool
    async def ask_grok(
        query: str,
        model: str = "grok-3-fast",
        system_prompt: Optional[str] = None,
    ) -> str:
        """Ask Grok and return plain text answer."""
        return await ask_grok_impl(query=query, model=model, system_prompt=system_prompt)


def create_mcp_http_app() -> Optional[Any]:
    if mcp is None:
        return None

    enabled = bool(get_config("mcp.enabled", True))
    if not enabled:
        return None

    try:
        return mcp.http_app(stateless_http=True, transport="streamable-http")
    except TypeError:
        return mcp.http_app(transport="streamable-http")
    except Exception as e:
        logger.warning(f"Failed to create MCP HTTP app: {e}")
        return None


__all__ = ["mcp", "create_mcp_server", "create_mcp_http_app"]
