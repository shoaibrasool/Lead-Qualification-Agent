from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    session_id: str
    message: str


class ChatResponse(BaseModel):
    reply: str
    session_id: str
    done: bool = False
    booking_link: str | None = None


class LeadInDB(BaseModel):
    session_id: str
    fields: dict[str, str | int | float | bool | None]
    score: int | None = None
    outcome: str | None = None
    booking_link: str | None = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
