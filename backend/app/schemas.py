from typing import Any, Optional
from pydantic import BaseModel


class ChatRequest(BaseModel):
    user_id: str
    conversation_id: Optional[str] = None
    message: str


class Citation(BaseModel):
    label: str
    url: Optional[str] = None


class ChatResponse(BaseModel):
    conversation_id: str
    intent: str
    reply: str
    citations: list[Citation] = []
    blocked: bool = False


class ScenarioRequest(BaseModel):
    tax_year: int
    filing_status: str
    changes: dict[str, Any] = {}


class SourceRegistryIn(BaseModel):
    domain: str
    description: str
    scope_tags: list[str] = []
    api_method: str
    enabled: bool = True
    tier: list[str] = ["basic", "plus", "pro"]


class SourceRegistryOut(SourceRegistryIn):
    id: str

    class Config:
        from_attributes = True
