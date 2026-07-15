from __future__ import annotations

import logging

from fastapi import APIRouter, Request
from langchain_core.messages import HumanMessage

from app.models import ChatRequest, ChatResponse

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/health")
async def health():
    return {"status": "ok"}


@router.post("/chat", response_model=ChatResponse)
async def chat(body: ChatRequest, request: Request):
    graph = request.app.state.graph
    config = {"configurable": {"thread_id": body.session_id}}

    try:
        current = graph.get_state(config)
        has_state = current is not None and len(current.values.get("messages", [])) > 0
    except Exception:
        has_state = False

    if has_state:
        result = await graph.ainvoke(
            {"messages": [HumanMessage(content=body.message)]},
            config,
        )
    else:
        result = await graph.ainvoke(
            {
                "messages": [HumanMessage(content=body.message)],
                "session_id": body.session_id,
                "collected_fields": {},
                "score": None,
                "outcome": None,
                "turn_count": 0,
                "booking_link": None,
                "complete": False,
                "score_breakdown": None,
                "pending_slots": None,
                "pending_selected_slot": None,
                "booking_error": None,
            },
            config,
        )

    messages = result.get("messages", [])
    reply = messages[-1].content if messages else ""
    outcome = result.get("outcome")
    pending_slots = result.get("pending_slots")
    pending_selected = result.get("pending_selected_slot")
    done = outcome is not None and pending_slots is None and pending_selected is None
    booking_link = result.get("booking_link")

    debug = {
        "outcome": outcome,
        "score": result.get("score"),
        "score_breakdown": result.get("score_breakdown"),
        "complete": result.get("complete"),
        "turn_count": result.get("turn_count"),
        "collected_fields": result.get("collected_fields"),
        "booking_error": result.get("booking_error"),
    }

    logger.info(
        "Session=%s outcome=%s score=%s complete=%s turn=%d",
        body.session_id, outcome, result.get("score"),
        result.get("complete"), result.get("turn_count", 0),
    )

    return ChatResponse(
        reply=reply,
        session_id=body.session_id,
        done=done,
        booking_link=booking_link,
        debug=debug,
    )
