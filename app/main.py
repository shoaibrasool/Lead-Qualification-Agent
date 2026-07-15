from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.mongodb import MongoDBSaver

from app.config import get_settings
from app.database import close_db, get_client, init_db
from app.graph.agent import build_graph
from app.models import ChatRequest, ChatResponse

logger = logging.getLogger(__name__)

_graph_instance = None


def get_graph():
    global _graph_instance
    return _graph_instance


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _graph_instance

    try:
        init_db()
        client = get_client()
        checkpointer = MongoDBSaver(client)
        _graph_instance = build_graph(checkpointer)
        logger.info("MongoDB checkpointer connected and graph compiled")
    except Exception as e:
        logger.warning("MongoDB unavailable, running without persistence: %s", e)
        _graph_instance = build_graph(None)

    yield

    close_db()


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="Lead Qualification Agent",
        version="1.0.0",
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    @app.post("/chat", response_model=ChatResponse)
    async def chat(body: ChatRequest):
        graph = get_graph()
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

        return ChatResponse(
            reply=reply,
            session_id=body.session_id,
            done=done,
            booking_link=booking_link,
        )

    return app


app = create_app()
