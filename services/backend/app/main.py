from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.services.mcp.server import mcp_http_app, trader_mcp

settings = get_settings()
configure_logging()

@asynccontextmanager
async def lifespan(_: FastAPI):
    async with trader_mcp.session_manager.run():
        yield


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Mcp-Session-Id"],
)

app.include_router(api_router, prefix="/api/v1")
app.mount("/mcp", mcp_http_app)


@app.get("/")
def root() -> dict:
    return {"name": settings.app_name, "status": "ok", "docs": "/docs"}
