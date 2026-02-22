"""
schemas.py — Pydantic models for API requests and responses.
"""

from pydantic import BaseModel


class Message(BaseModel):
    role: str
    content: str | None = None


class ChatRequest(BaseModel):
    model: str = "gtfs-agent"
    messages: list[Message]
    stream: bool = False
    temperature: float | None = None
    max_tokens: int | None = None
