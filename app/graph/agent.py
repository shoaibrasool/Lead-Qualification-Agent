from __future__ import annotations

from typing import Optional

from langgraph.checkpoint.mongodb import MongoDBSaver
from langgraph.graph import END, StateGraph, START

from app.graph.edges import route_after_booking, route_after_collect, route_after_score
from app.graph.nodes import collect_info_node, greet_node, score_lead_node
from app.graph.state import LeadState


def book_demo_node(state: LeadState) -> dict:
    return {}


def notify_slack_node(state: LeadState) -> dict:
    return {}


def end_node(state: LeadState) -> dict:
    return {}


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
        "score_lead": "score_lead",
        END: END,
    })
    builder.add_conditional_edges("score_lead", route_after_score, {
        "book_demo": "book_demo",
        "notify_slack": "notify_slack",
        END: END,
    })
    builder.add_conditional_edges("book_demo", route_after_booking, {
        "notify_slack": "notify_slack",
        END: END,
    })
    builder.add_edge("notify_slack", "end")
    builder.add_edge("end", END)

    compile_kwargs = {}
    if checkpointer is not None:
        compile_kwargs["checkpointer"] = checkpointer

    graph = builder.compile(**compile_kwargs)
    return graph
