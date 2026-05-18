"""Helpers for parsing LangGraph message traces into API-friendly structures."""

import re

from langchain_core.messages import AIMessage, ToolMessage

from backend.api.schemas import ToolCallRecord

_ERROR_PREFIXES = ("SQL ERROR:", "MONGO ERROR:", "SEARCH ERROR:")


def extract_tool_calls(messages: list) -> tuple[list[ToolCallRecord], list[str]]:
    """
    Parse LangGraph messages into ordered tool-call records and user warnings.

    Warnings are suppressed when a tool call fails but a later call to the same
    tool in the same turn succeeds.
    """
    tool_results: dict[str, str] = {}
    for msg in messages:
        if isinstance(msg, ToolMessage):
            tool_results[msg.tool_call_id] = str(msg.content)

    records: list[ToolCallRecord] = []
    provisional_warnings: list[tuple[int, str, str]] = []
    success_indices_by_tool: dict[str, list[int]] = {}

    for msg in messages:
        if not isinstance(msg, AIMessage) or not msg.tool_calls:
            continue

        for tc in msg.tool_calls:
            tool_name = tc["name"]
            tool_args = tc.get("args", {})
            call_id = tc.get("id", "")
            result_str = tool_results.get(call_id, "(no result captured)")

            records.append(ToolCallRecord(tool=tool_name, args=tool_args, result=result_str))
            record_index = len(records) - 1

            warning_message = _warning_message(tool_name, result_str)
            if warning_message:
                provisional_warnings.append((record_index, tool_name, warning_message))
            elif _is_successful_result(result_str):
                success_indices_by_tool.setdefault(tool_name, []).append(record_index)

    final_warnings: list[str] = []
    for warning_index, tool_name, warning_message in provisional_warnings:
        success_indices = success_indices_by_tool.get(tool_name, [])
        recovered_later = any(success_index > warning_index for success_index in success_indices)
        if not recovered_later:
            final_warnings.append(warning_message)

    return records, final_warnings


def get_final_answer(messages: list) -> str:
    """Return the last non-tool-calling AI answer from LangGraph messages."""
    for msg in reversed(messages):
        if isinstance(msg, AIMessage) and not msg.tool_calls:
            content = msg.content
            if isinstance(content, str):
                return content
            if isinstance(content, list):
                return " ".join(
                    block.get("text", "") if isinstance(block, dict) else str(block)
                    for block in content
                )
    return "No answer produced."


def normalize_answer_text(answer: str) -> str:
    """Convert markdown-like list formatting into plain chatbot text."""
    cleaned_lines: list[str] = []
    for raw_line in answer.splitlines():
        line = re.sub(r"^\s*[*-]\s+", "", raw_line).strip()
        if line:
            cleaned_lines.append(line)
    if not cleaned_lines:
        return answer.strip()
    return " ".join(cleaned_lines)


def _warning_message(tool_name: str, result_str: str) -> str | None:
    if result_str.startswith("REFUSED:"):
        return f"[{tool_name}] {result_str}"
    if any(result_str.startswith(prefix) for prefix in _ERROR_PREFIXES):
        return f"[{tool_name}] {result_str}"
    if result_str in ("[]", "null", ""):
        return f"[{tool_name}] returned no results"
    return None


def _is_successful_result(result_str: str) -> bool:
    if result_str in ("", "[]", "null", "(no result captured)"):
        return False
    if result_str.startswith("REFUSED:"):
        return False
    if any(result_str.startswith(prefix) for prefix in _ERROR_PREFIXES):
        return False
    return True

