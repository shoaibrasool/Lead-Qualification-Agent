from __future__ import annotations

import logging

from pymongo import MongoClient

from app.config import get_settings

logger = logging.getLogger(__name__)

_client: MongoClient | None = None

_TLS_PARAMS = "tlsInsecure=true"


def get_client() -> MongoClient:
    global _client
    if _client is None:
        settings = get_settings()
        uri = settings.mongodb_connection_string.get_secret_value()
        separator = "&" if "?" in uri else "?"
        uri = f"{uri}{separator}{_TLS_PARAMS}"
        _client = MongoClient(uri, serverSelectionTimeoutMS=10000)
    return _client


def get_leads_collection():
    settings = get_settings()
    return get_client()[settings.app_env]["leads"]


def init_db():
    settings = get_settings()
    db = get_client()[settings.app_env]
    leads = db["leads"]
    existing = leads.index_information()
    if "session_id_1" not in existing:
        leads.create_index("session_id", unique=True)
    if "timestamp_1" not in existing:
        leads.create_index("timestamp")
    if "outcome_1" not in existing:
        leads.create_index("outcome")
    logger.info("Database indexes ensured")


def close_db():
    global _client
    if _client is not None:
        _client.close()
        _client = None
        logger.info("MongoDB client closed")
