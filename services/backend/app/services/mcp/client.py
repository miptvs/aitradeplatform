import asyncio
import json
import logging
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from app.core.config import get_settings


logger = logging.getLogger(__name__)
settings = get_settings()


class MCPClientService:
    def is_enabled(self) -> bool:
        return settings.mcp_enabled

    @asynccontextmanager
    async def _session(self) -> AsyncIterator[ClientSession]:
        timeout = httpx.Timeout(settings.mcp_request_timeout_seconds, connect=settings.mcp_connect_timeout_seconds)
        async with httpx.AsyncClient(timeout=timeout) as http_client:
            async with streamable_http_client(settings.mcp_server_url, http_client=http_client) as (
                read_stream,
                write_stream,
                _,
            ):
                async with ClientSession(read_stream, write_stream) as session:
                    await session.initialize()
                    yield session

    async def _get_status_async(self) -> dict[str, Any]:
        if not self.is_enabled():
            return {
                "enabled": False,
                "reachable": False,
                "server_url": settings.mcp_server_url,
                "transport": "streamable-http",
                "message": "MCP integration is disabled by configuration.",
                "server_name": None,
                "tools": [],
                "resources": [],
            }

        try:
            async with self._session() as session:
                tools_response = await session.list_tools()
                resources_response = await session.list_resources()
                return {
                    "enabled": True,
                    "reachable": True,
                    "server_url": settings.mcp_server_url,
                    "transport": "streamable-http",
                    "message": f"Connected to MCP server at {settings.mcp_server_url}.",
                    "server_name": "AI Trader Platform MCP",
                    "tools": [
                        {"name": tool.name, "description": tool.description}
                        for tool in tools_response.tools
                    ],
                    "resources": [
                        {"uri": str(resource.uri), "name": resource.name, "description": resource.description}
                        for resource in resources_response.resources
                    ],
                }
        except Exception as exc:
            logger.warning("MCP status check failed: %s", exc)
            return {
                "enabled": True,
                "reachable": False,
                "server_url": settings.mcp_server_url,
                "transport": "streamable-http",
                "message": str(exc),
                "server_name": None,
                "tools": [],
                "resources": [],
            }

    async def _call_tool_async(self, tool_name: str, arguments: dict[str, Any]) -> Any:
        async with self._session() as session:
            result = await session.call_tool(tool_name, arguments=arguments)
            structured = getattr(result, "structuredContent", None)
            if structured is not None:
                return structured

            text_parts: list[str] = []
            for content in getattr(result, "content", []):
                text = getattr(content, "text", None)
                if text:
                    text_parts.append(text)
            if not text_parts:
                return None

            joined = "\n".join(text_parts)
            try:
                return json.loads(joined)
            except Exception:
                return {"text": joined}

    def _run(self, coro):
        return asyncio.run(coro)

    def get_status(self) -> dict[str, Any]:
        return self._run(self._get_status_async())

    def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> Any:
        if not self.is_enabled():
            raise ValueError("MCP integration is disabled")
        return self._run(self._call_tool_async(tool_name, arguments))

    def get_signal_context(self, *, symbol: str, mode: str) -> dict[str, Any] | None:
        if not self.is_enabled():
            return None
        try:
            result = self.call_tool("get_signal_context", {"symbol": symbol, "mode": mode})
            return result if isinstance(result, dict) else None
        except Exception as exc:
            logger.warning("MCP signal context lookup failed for %s: %s", symbol, exc)
            return None


mcp_client_service = MCPClientService()
