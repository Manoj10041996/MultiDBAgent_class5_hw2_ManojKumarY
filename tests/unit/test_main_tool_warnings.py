"""
Unit tests for warning extraction logic in backend.main._extract_tool_calls.
"""

from langchain_core.messages import AIMessage, ToolMessage

from backend.main import _extract_tool_calls


def test_suppresses_sql_warning_when_later_sql_call_succeeds():
    messages = [
        AIMessage(
            content="",
            tool_calls=[{
                "name": "sql_query",
                "args": {"sql": "bad query"},
                "id": "call_1",
                "type": "tool_call",
            }],
        ),
        ToolMessage(
            content="SQL ERROR: column c.customer_id does not exist",
            tool_call_id="call_1",
        ),
        AIMessage(
            content="",
            tool_calls=[{
                "name": "sql_query",
                "args": {"sql": "good query"},
                "id": "call_2",
                "type": "tool_call",
            }],
        ),
        ToolMessage(
            content='[{"customer_id": 4, "name": "David Lee", "order_count": 3}]',
            tool_call_id="call_2",
        ),
        AIMessage(content="Final answer"),
    ]

    records, warnings = _extract_tool_calls(messages)

    assert len(records) == 2
    assert warnings == []


def test_keeps_warning_when_sql_error_is_not_recovered():
    messages = [
        AIMessage(
            content="",
            tool_calls=[{
                "name": "sql_query",
                "args": {"sql": "bad query"},
                "id": "call_1",
                "type": "tool_call",
            }],
        ),
        ToolMessage(
            content="SQL ERROR: relation orders does not exist",
            tool_call_id="call_1",
        ),
        AIMessage(content="I could not retrieve the data."),
    ]

    _, warnings = _extract_tool_calls(messages)

    assert len(warnings) == 1
    assert "SQL ERROR" in warnings[0]
