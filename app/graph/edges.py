from __future__ import annotations

from typing import Literal

from langgraph.graph import END

from app.config import get_settings
from app.graph.nodes import _has_ai_reply
from app.graph.state import LeadState


def route_start(state: LeadState) -> Literal["greet", "collect_info"]:
    if _has_ai_reply(state.get("messages", [])):
        return "collect_info"
    return "greet"


def route_after_collect(state: LeadState) -> Literal["score_lead", "__end__"]:
    if state.get("outcome"):
        return END
    if state.get("complete"):
        return "score_lead"
    settings = get_settings()
    if state.get("turn_count", 0) >= settings.max_conversation_turns:
        return "score_lead"
    return END


def route_after_score(state: LeadState) -> Literal["book_demo", "notify_slack", "__end__"]:
    score = state.get("score") or 0
    settings = get_settings()
    if score >= settings.auto_book_threshold:
        return "book_demo"
    elif score >= settings.flag_followup_threshold:
        return "notify_slack"
    return END


def route_after_booking(state: LeadState) -> Literal["notify_slack", "__end__"]:
    if state.get("booking_link"):
        return "notify_slack"
    return END
