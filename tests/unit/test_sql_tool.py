"""
test_sql_tool.py — Unit tests for the sql_query tool.

All database calls are mocked. Tests cover:
  - Good input (valid SELECT)
  - LIMIT auto-injection
  - Aggregate queries (no LIMIT injected)
  - Non-SELECT statement
  - Multiple statements
  - Dangerous keyword (each forbidden keyword)
  - Postgres exception handling
  - Statement timeout handling
"""

from unittest.mock import MagicMock, patch

import pytest

from backend.tools.sql_tool import _inject_limit, _validate_sql, sql_query


# ---------------------------------------------------------------------------
# _validate_sql unit tests
# ---------------------------------------------------------------------------

class TestValidateSql:
    def test_valid_select_returns_none(self):
        assert _validate_sql("SELECT name FROM products") is None

    def test_valid_with_cte_returns_none(self):
        sql = "WITH top AS (SELECT id FROM orders LIMIT 5) SELECT * FROM top"
        assert _validate_sql(sql) is None

    def test_non_select_refused(self):
        result = _validate_sql("UPDATE products SET price = 0")
        assert result is not None
        assert "REFUSED" in result
        assert "SELECT" in result

    def test_empty_query_refused(self):
        result = _validate_sql("")
        assert result is not None
        assert "REFUSED" in result

    @pytest.mark.parametrize("kw", [
        "DROP", "DELETE", "INSERT", "UPDATE",
        "ALTER", "TRUNCATE", "GRANT", "REVOKE",
        "CREATE", "EXEC", "EXECUTE",
    ])
    def test_forbidden_keyword_refused(self, kw: str):
        sql = f"SELECT * FROM products; {kw} TABLE products"
        result = _validate_sql(sql)
        assert result is not None
        assert "REFUSED" in result
        assert kw in result

    def test_multiple_statements_refused(self):
        sql = "SELECT 1; SELECT 2"
        result = _validate_sql(sql)
        assert result is not None
        assert "REFUSED" in result
        assert "multiple" in result.lower()

    def test_trailing_semicolon_is_ok(self):
        # A single trailing semicolon is common and should be accepted
        sql = "SELECT name FROM products;"
        assert _validate_sql(sql) is None

    def test_drop_table_attack_refused(self):
        sql = "SELECT 1; DROP TABLE products --"
        result = _validate_sql(sql)
        assert result is not None
        assert "REFUSED" in result


# ---------------------------------------------------------------------------
# _inject_limit unit tests
# ---------------------------------------------------------------------------

class TestInjectLimit:
    def test_injects_limit_when_missing(self):
        sql = "SELECT name FROM products"
        result = _inject_limit(sql)
        assert "LIMIT" in result.upper()

    def test_does_not_double_inject(self):
        sql = "SELECT name FROM products LIMIT 10"
        result = _inject_limit(sql)
        assert result.upper().count("LIMIT") == 1

    def test_no_inject_for_count_aggregate(self):
        sql = "SELECT COUNT(*) FROM orders"
        result = _inject_limit(sql)
        assert "LIMIT" not in result.upper()

    def test_no_inject_for_group_by(self):
        sql = "SELECT status, COUNT(*) FROM orders GROUP BY status"
        result = _inject_limit(sql)
        assert "LIMIT" not in result.upper()

    def test_no_inject_for_sum(self):
        sql = "SELECT SUM(total) FROM orders"
        result = _inject_limit(sql)
        assert "LIMIT" not in result.upper()


# ---------------------------------------------------------------------------
# sql_query tool integration (mocked DB)
# ---------------------------------------------------------------------------

class TestSqlQueryTool:
    @patch("backend.tools.sql_tool.psycopg2.connect")
    def test_good_query_returns_json(self, mock_connect):
        # Arrange
        mock_cur = MagicMock()
        mock_cur.fetchall.return_value = [{"name": "Wireless Mouse", "stock_qty": 142}]
        mock_conn = MagicMock()
        mock_conn.__enter__ = lambda s: s
        mock_conn.__exit__ = MagicMock(return_value=False)
        mock_conn.cursor.return_value.__enter__ = lambda s: mock_cur
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_connect.return_value = mock_conn

        result = sql_query.invoke({"sql": "SELECT name, stock_qty FROM products"})

        assert "Wireless Mouse" in result
        assert "142" in result

    def test_drop_table_refused(self):
        result = sql_query.invoke({"sql": "DROP TABLE products"})
        assert result.startswith("REFUSED")

    def test_insert_refused(self):
        result = sql_query.invoke({"sql": "INSERT INTO products VALUES (1, 'test', 'cat', 10.0, 5)"})
        assert result.startswith("REFUSED")

    def test_multiple_statements_refused(self):
        result = sql_query.invoke({"sql": "SELECT 1; DELETE FROM orders"})
        assert result.startswith("REFUSED")

    @patch("backend.tools.sql_tool.psycopg2.connect")
    def test_postgres_error_returns_sql_error_string(self, mock_connect):
        import psycopg2
        mock_connect.side_effect = psycopg2.OperationalError("connection refused")
        result = sql_query.invoke({"sql": "SELECT name FROM products"})
        assert result.startswith("SQL ERROR")

    @patch("backend.tools.sql_tool.psycopg2.connect")
    def test_timeout_returns_error_string(self, mock_connect):
        import psycopg2
        mock_cur = MagicMock()
        mock_cur.execute.side_effect = [None, psycopg2.errors.QueryCanceled()]
        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__ = lambda s: mock_cur
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_connect.return_value = mock_conn

        result = sql_query.invoke({"sql": "SELECT pg_sleep(10)"})
        assert "timeout" in result.lower() or result.startswith("SQL ERROR")
