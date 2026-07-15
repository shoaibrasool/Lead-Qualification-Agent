from __future__ import annotations

from typing import Annotated, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class LeadState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    session_id: str
    collected_fields: dict[str, str | int | float | bool | None]
    score: int | None
    outcome: str | None
    turn_count: int
    booking_link: str | None
    complete: bool
    score_breakdown: list[dict] | None
    pending_slots: list[dict] | None
    pending_selected_slot: dict | None
    booking_error: str | None
