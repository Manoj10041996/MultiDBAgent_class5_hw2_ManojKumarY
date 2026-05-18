"""
Thin ASGI entrypoint for backward compatibility.

`uvicorn backend.main:app` remains valid while implementation lives under
`backend/api/`.
"""

from backend.api.app import app
from backend.api.message_parser import extract_tool_calls as _extract_tool_calls
from backend.api.message_parser import get_final_answer as _get_final_answer
from backend.api.message_parser import normalize_answer_text as _normalize_answer_text

