from __future__ import annotations

from typing import Optional

from langgraph.checkpoint.mongodb import MongoDBSaver
from langgraph.graph import END, StateGraph, START

from app.config import get_settings
from app.graph.state import LeadState


def greet_node(state: LeadState) -> dict:
    from langchain_core.messages import AIMessage
    return {
        "messages": [AIMessage(content="Hi! I'm here to help qualify your lead. Let's start with some questions.")],
        "turn_count": 0,
    }


def collect_info_node(state: LeadState) -> dict:
    return {
        "turn_count": state.get("turn_count", 0) + 1,
    }


def score_lead_node(state: LeadState) -> dict:
    return {
        "score": 0,
    }


def book_demo_node(state: LeadState) -> dict:
    return {}


def notify_slack_node(state: LeadState) -> dict:
    return {}


def end_node(state: LeadState) -> dict:
    return {}


def route_after_score(state: LeadState) -> str:
    score = state.get("score") or 0
    settings = get_settings()
    if score >= settings.auto_book_threshold:
        return "book_demo"
    elif score >= settings.flag_followup_threshold:
        return "notify_slack"
    return "end"


def route_after_booking(state: LeadState) -> str:
    if state.get("booking_link"):
        return "notify_slack"
    return "end"


def route_after_collect(state: LeadState) -> str:
    settings = get_settings()
    turn_count = state.get("turn_count", 0)
    if turn_count >= settings.max_conversation_turns:
        return "score_lead"
    return "collect_info"


def build_graph(checkpointer: Optional[MongoDBSaver]):
    builder = StateGraph(LeadState)

    builder.add_node("greet", greet_node, run_timeout=10)
    builder.add_node("collect_info", collect_info_node, run_timeout=30)
    builder.add_node("score_lead", score_lead_node, run_timeout=10)
    builder.add_node("book_demo", book_demo_node, run_timeout=30)
    builder.add_node("notify_slack", notify_slack_node, run_timeout=30)
    builder.add_node("end", end_node, run_timeout=5)

    builder.add_edge(START, "greet")
    builder.add_edge("greet", "collect_info")
    builder.add_conditional_edges("collect_info", route_after_collect, {
        "collect_info": "collect_info",
        "score_lead": "score_lead",
    })
    builder.add_conditional_edges("score_lead", route_after_score, {
        "book_demo": "book_demo",
        "notify_slack": "notify_slack",
        "end": "end",
    })
    builder.add_conditional_edges("book_demo", route_after_booking, {
        "notify_slack": "notify_slack",
        "end": "end",
    })
    builder.add_edge("notify_slack", "end")
    builder.add_edge("end", END)

    compile_kwargs = {}
    if checkpointer is not None:
        compile_kwargs["checkpointer"] = checkpointer

    graph = builder.compile(**compile_kwargs)
    return graph
