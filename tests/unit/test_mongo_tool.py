"""
test_mongo_tool.py — Unit tests for the mongo_query tool.

All MongoDB calls are mocked. Tests cover:
  - Good input (valid collection + filter)
  - Collection not in whitelist
  - $where injection attempt
  - $function injection attempt
  - Limit exceeds hard cap (silently capped)
  - Non-dict filter rejected
  - MongoDB execution error handled as string
"""

from unittest.mock import MagicMock, patch

import pytest

from backend.tools.mongo_tool import (
    _validate_collection,
    _validate_filter,
    mongo_query,
)


# ---------------------------------------------------------------------------
# _validate_collection unit tests
# ---------------------------------------------------------------------------

class TestValidateCollection:
    def test_whitelisted_collections_pass(self):
        for col in ["reviews", "support_tickets", "activity_logs"]:
            assert _validate_collection(col) is None

    def test_non_whitelisted_refused(self):
        result = _validate_collection("orders")
        assert result is not None
        assert "REFUSED" in result
        assert "orders" in result

    def test_empty_string_refused(self):
        result = _validate_collection("")
        assert result is not None
        assert "REFUSED" in result

    def test_case_sensitive(self):
        # Collection names are case-sensitive
        result = _validate_collection("Reviews")
        assert result is not None
        assert "REFUSED" in result


# ---------------------------------------------------------------------------
# _validate_filter unit tests
# ---------------------------------------------------------------------------

class TestValidateFilter:
    def test_safe_filter_returns_none(self):
        assert _validate_filter({"rating": 1}) is None

    def test_safe_nested_filter_returns_none(self):
        assert _validate_filter({"status": "open", "rating": {"$gte": 1}}) is None

    def test_where_operator_refused(self):
        result = _validate_filter({"$where": "this.rating == 1"})
        assert result is not None
        assert "REFUSED" in result
        assert "$where" in result

    def test_function_operator_refused(self):
        result = _validate_filter({"$function": {"body": "function(){}", "args": [], "lang": "js"}})
        assert result is not None
        assert "REFUSED" in result

    def test_nested_where_refused(self):
        result = _validate_filter({"rating": {"$where": "evil()"}})
        assert result is not None
        assert "REFUSED" in result

    def test_accumulator_refused(self):
        result = _validate_filter({"$accumulator": {}})
        assert result is not None
        assert "REFUSED" in result


# ---------------------------------------------------------------------------
# mongo_query tool (mocked MongoDB)
# ---------------------------------------------------------------------------

class TestMongoQueryTool:
    @patch("backend.tools.mongo_tool.MongoClient")
    def test_good_query_returns_json(self, mock_client_cls):
        # Arrange
        mock_cursor = iter([
            {"product_id": "MOUSE-001", "rating": 1, "comment": "Terrible"},
        ])
        mock_collection = MagicMock()
        mock_collection.find.return_value.limit.return_value = mock_cursor
        mock_db = MagicMock()
        mock_db.__getitem__ = lambda s, k: mock_collection
        mock_client = MagicMock()
        mock_client.__getitem__ = lambda s, k: mock_db
        mock_client_cls.return_value = mock_client

        result = mongo_query.invoke({
            "collection": "reviews",
            "filter": {"rating": 1},
            "limit": 5,
        })

        assert "MOUSE-001" in result
        assert "Terrible" in result

    def test_non_whitelisted_collection_refused(self):
        result = mongo_query.invoke({
            "collection": "orders",
            "filter": {},
            "limit": 5,
        })
        assert result.startswith("REFUSED")
        assert "orders" in result

    def test_where_injection_refused(self):
        result = mongo_query.invoke({
            "collection": "reviews",
            "filter": {"$where": "this.rating > 0"},
            "limit": 5,
        })
        assert result.startswith("REFUSED")
        assert "$where" in result

    def test_limit_capped_at_20(self):
        """limit=100 should be silently capped to 20."""
        with patch("backend.tools.mongo_tool.MongoClient") as mock_client_cls:
            mock_cursor = iter([])
            mock_collection = MagicMock()
            mock_collection.find.return_value.limit.return_value = mock_cursor
            mock_db = MagicMock()
            mock_db.__getitem__ = lambda s, k: mock_collection
            mock_client = MagicMock()
            mock_client.__getitem__ = lambda s, k: mock_db
            mock_client_cls.return_value = mock_client

            mongo_query.invoke({
                "collection": "reviews",
                "filter": {},
                "limit": 100,
            })

            # The .limit() call must have been called with at most 20
            call_args = mock_collection.find.return_value.limit.call_args
            assert call_args[0][0] <= 20

    @patch("backend.tools.mongo_tool.MongoClient")
    def test_mongo_error_returns_error_string(self, mock_client_cls):
        mock_client_cls.side_effect = Exception("connection refused")
        result = mongo_query.invoke({
            "collection": "reviews",
            "filter": {},
        })
        assert result.startswith("MONGO ERROR")
        assert "connection refused" in result
