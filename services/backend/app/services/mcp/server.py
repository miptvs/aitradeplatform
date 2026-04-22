import json

from mcp.server.fastmcp import FastMCP

from app.core.database import SessionLocal
from app.services.mcp.context_tools import build_architecture_payload, build_signal_context_payload


trader_mcp = FastMCP(
    "AI Trader Platform MCP",
    stateless_http=True,
    json_response=True,
)
trader_mcp.settings.streamable_http_path = "/"
trader_mcp.settings.transport_security.allowed_hosts.extend(
    [
        "backend:*",
        "ai-trader-backend:*",
        "host.docker.internal:*",
    ]
)
trader_mcp.settings.transport_security.allowed_origins.extend(
    [
        "http://backend:*",
        "http://ai-trader-backend:*",
        "http://host.docker.internal:*",
    ]
)


@trader_mcp.tool()
def get_signal_context(symbol: str, mode: str = "simulation") -> dict:
    """Return normalized trading context for one symbol, including prices, news, events, risk rules, and open positions."""
    with SessionLocal() as db:
        return build_signal_context_payload(db, symbol=symbol, mode=mode)


@trader_mcp.tool()
def get_architecture_snapshot() -> dict:
    """Return the current runtime topology, provider catalog, broker accounts, and simulation accounts."""
    with SessionLocal() as db:
        return build_architecture_payload(db)


@trader_mcp.resource("platform://architecture")
def architecture_resource() -> str:
    """Read the current platform runtime architecture as JSON."""
    with SessionLocal() as db:
        return json.dumps(build_architecture_payload(db), indent=2)


mcp_http_app = trader_mcp.streamable_http_app()
