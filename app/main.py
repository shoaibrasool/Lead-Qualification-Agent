from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    force=True,
)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from langgraph.checkpoint.mongodb import MongoDBSaver

from app.config import get_settings
from app.database import close_db, get_client, init_db
from app.graph.agent import build_graph
from app.routes.chat import router as chat_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        init_db()
        client = get_client()
        checkpointer = MongoDBSaver(client)
        app.state.graph = build_graph(checkpointer)
        logger.info("MongoDB checkpointer connected and graph compiled")
    except Exception as e:
        logger.warning("MongoDB unavailable, running without persistence: %s", e)
        app.state.graph = build_graph(None)

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

    app.include_router(chat_router)

    return app


app = create_app()
