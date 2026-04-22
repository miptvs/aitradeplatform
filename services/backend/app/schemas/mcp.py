from pydantic import BaseModel, Field


class McpToolRead(BaseModel):
    name: str
    description: str | None = None


class McpResourceRead(BaseModel):
    uri: str
    name: str | None = None
    description: str | None = None


class McpStatusRead(BaseModel):
    enabled: bool
    reachable: bool
    server_url: str
    transport: str = "streamable-http"
    message: str
    server_name: str | None = None
    tools: list[McpToolRead] = Field(default_factory=list)
    resources: list[McpResourceRead] = Field(default_factory=list)
