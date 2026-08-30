"""Mongo connection + shared helpers for the emm-mongo MCP server."""

import os
from pathlib import Path
from datetime import datetime, timezone

from dotenv import load_dotenv
from pymongo import MongoClient

REPO_ROOT = Path(__file__).resolve().parents[2]

load_dotenv(Path(__file__).resolve().parent / ".env")

MONGODB_URI = os.environ.get("MONGODB_URI", "mongodb://localhost:27017")
MONGODB_DB = os.environ.get("MONGODB_DB", "emm")

_client = None


def get_db():
    global _client
    if _client is None:
        _client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
    return _client[MONGODB_DB]


def inventory_collection():
    return get_db()["inventory"]


def transactions_collection():
    return get_db()["transactions"]


def scion_sales_collection():
    return get_db()["scion_sales"]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


VALID_CATEGORIES = {"trees-scions", "fresh-fruit", "vegetables-herbs", "cottage-foods"}
VALID_PROPAGATION = {"grafted", "seed", "unknown"}
VALID_STATUS = {"active", "seasonal", "coming-soon"}
VALID_CHANGE_TYPES = {"initial", "restock", "sale",
                       "adjustment", "loss", "transfer"}


def strip_mongo_id(doc: dict) -> dict:
    doc = dict(doc)
    doc.pop("_id", None)
    return doc
