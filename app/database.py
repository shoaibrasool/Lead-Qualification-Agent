from __future__ import annotations

import logging
import ssl

from pymongo import MongoClient

from app.config import get_settings

logger = logging.getLogger(__name__)

_client: MongoClient | None = None


def _make_ssl_context() -> ssl.SSLContext:
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    return ctx


def get_client() -> MongoClient:
    global _client
    if _client is None:
        settings = get_settings()
        _client = MongoClient(
            settings.mongodb_connection_string.get_secret_value(),
            serverSelectionTimeoutMS=10000,
            tls=True,
            ssl_context=_make_ssl_context(),
        )
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
