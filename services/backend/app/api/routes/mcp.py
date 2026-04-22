from fastapi import APIRouter

from app.schemas.mcp import McpStatusRead
from app.services.mcp.client import mcp_client_service


router = APIRouter()


@router.get("/status", response_model=McpStatusRead)
def mcp_status() -> McpStatusRead:
    return McpStatusRead.model_validate(mcp_client_service.get_status())
