"""
mongo_tool.py — Typed MongoDB query tool for StockPulse.

Security guarantees:
  - Collection whitelist: only reviews, support_tickets, activity_logs.
  - Filter safety: blocks server-side JS operators ($where, $function, $accumulator).
  - Hard cap on returned documents (max 20).
  - No aggregation pipelines exposed to the LLM (find() only).
  - Returns a plain string in every code path — the ReAct loop never crashes.
"""

import json
from datetime import datetime
from typing import Any

from bson import ObjectId
from langchain_core.tools import tool
from pymongo import MongoClient

from backend.config import settings

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

WHITELISTED_COLLECTIONS = {"reviews", "support_tickets", "activity_logs"}

# Operators that execute arbitrary JS on the server
BLOCKED_FILTER_OPERATORS = {"$where", "$function", "$accumulator", "$expr"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _validate_collection(collection: str) -> str | None:
    if collection not in WHITELISTED_COLLECTIONS:
        allowed = ", ".join(sorted(WHITELISTED_COLLECTIONS))
        return f"REFUSED: collection '{collection}' is not whitelisted. Allowed: {allowed}"
    return None


def _validate_filter(filter_doc: dict, _depth: int = 0) -> str | None:
    """
    Recursively walks the filter document looking for blocked operators.
    Depth-limited to prevent DoS via deeply nested docs.
    """
    if _depth > 10:
        return "REFUSED: filter document is too deeply nested"

    for key, value in filter_doc.items():
        if key in BLOCKED_FILTER_OPERATORS:
            return f"REFUSED: operator '{key}' is not allowed (server-side JS blocked)"
        if isinstance(value, dict):
            result = _validate_filter(value, _depth + 1)
            if result:
                return result
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    result = _validate_filter(item, _depth + 1)
                    if result:
                        return result
    return None


def _serialize_doc(doc: dict[str, Any]) -> dict[str, Any]:
    """Converts MongoDB-specific types to JSON-safe equivalents."""
    out = {}
    for k, v in doc.items():
        if isinstance(v, ObjectId):
            out[k] = str(v)
        elif isinstance(v, datetime):
            out[k] = v.isoformat()
        elif isinstance(v, dict):
            out[k] = _serialize_doc(v)
        elif isinstance(v, list):
            out[k] = [
                _serialize_doc(i) if isinstance(i, dict) else str(i) if isinstance(i, (ObjectId, datetime)) else i
                for i in v
            ]
        else:
            out[k] = v
    return out


# ---------------------------------------------------------------------------
# Tool
# ---------------------------------------------------------------------------

@tool
def mongo_query(collection: str, filter: dict, limit: int = 10) -> str:
    """
    Query a MongoDB collection in the StockPulse database.

    Use this tool for questions about customer reviews, star ratings,
    complaints, support tickets, refund requests, or user activity logs.

    Args:
        collection: One of 'reviews', 'support_tickets', 'activity_logs'.
        filter: A MongoDB filter document, e.g. {"rating": 1} or {"status": "open"}.
        limit: Maximum number of documents to return (default 10, hard cap 20).

    Returns:
        A JSON-serialised list of documents, or a REFUSED/MONGO ERROR string.
    """
    # --- Validate collection ---
    col_error = _validate_collection(collection)
    if col_error:
        return col_error

    # --- Validate filter ---
    if not isinstance(filter, dict):
        return "REFUSED: filter must be a JSON object (dict)"
    filter_error = _validate_filter(filter)
    if filter_error:
        return filter_error

    # --- Enforce limit cap ---
    capped_limit = min(max(1, limit), settings.mongo_doc_limit)

    # --- Execute ---
    client = None
    try:
        client = MongoClient(settings.mongo_url, serverSelectionTimeoutMS=5000)
        db = client[settings.mongo_db]
        cursor = db[collection].find(filter, {"_id": 0}).limit(capped_limit)
        docs = [_serialize_doc(doc) for doc in cursor]
        return json.dumps(docs, default=str)

    except Exception as exc:
        return f"MONGO ERROR: {str(exc)}"
    finally:
        if client:
            client.close()
