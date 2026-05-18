"""
sql_tool.py — Read-only SELECT tool against Postgres.

Security guarantees:
  - Rejects any query containing forbidden DML/DDL keywords.
  - Rejects multiple statements (semicolon in body).
  - Only allows queries that start with SELECT or WITH.
  - Auto-injects LIMIT if missing (prevents accidental full-table scans).
  - Enforces a statement-level timeout via Postgres SET LOCAL.
  - Returns a plain string in every code path — the ReAct loop never crashes.
"""

import json
import re
from typing import Any

import psycopg2
import psycopg2.extras
from langchain_core.tools import tool

from backend.config import settings

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

FORBIDDEN_KEYWORDS = [
    "DROP", "DELETE", "INSERT", "UPDATE", "ALTER",
    "TRUNCATE", "GRANT", "REVOKE", "CREATE", "REPLACE",
    "EXEC", "EXECUTE", "CALL",
]

# Matches a bare semicolon that is NOT at the very end of the stripped string
# (i.e., detects multiple statements)
_MULTI_STMT_RE = re.compile(r";(?!\s*$)")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _validate_sql(sql: str) -> str | None:
    """
    Returns a REFUSED/ERROR string if the query is unsafe, else None.
    """
    sql_stripped = sql.strip()

    # Must start with SELECT or WITH (CTEs allowed)
    first_word = sql_stripped.split()[0].upper() if sql_stripped else ""
    if first_word not in ("SELECT", "WITH"):
        return "REFUSED: only SELECT (or WITH …) statements are allowed"

    # Forbidden keywords anywhere in the query
    upper = sql_stripped.upper()
    for kw in FORBIDDEN_KEYWORDS:
        # Word-boundary match to avoid false positives like "SELECTED"
        if re.search(rf"\b{kw}\b", upper):
            return f"REFUSED: query contains forbidden keyword '{kw}'"

    # Multiple statements
    if _MULTI_STMT_RE.search(sql_stripped):
        return "REFUSED: multiple statements are not allowed"

    return None  # safe


def _inject_limit(sql: str) -> str:
    """
    Auto-appends LIMIT if the query has no LIMIT clause and is not an
    aggregate (GROUP BY / HAVING / aggregate functions).
    """
    upper = sql.upper()
    has_limit = "LIMIT" in upper
    is_aggregate = any(kw in upper for kw in ("GROUP BY", "HAVING", "COUNT(", "SUM(", "AVG(", "MAX(", "MIN("))
    if not has_limit and not is_aggregate:
        return sql.rstrip().rstrip(";") + f" LIMIT {settings.sql_row_limit}"
    return sql


def _rows_to_json(cursor) -> str:
    """Fetches all rows from cursor and JSON-serialises them."""
    rows: list[dict[str, Any]] = cursor.fetchall()
    return json.dumps(rows, default=str)


# ---------------------------------------------------------------------------
# Tool
# ---------------------------------------------------------------------------

@tool
def sql_query(sql: str) -> str:
    """
    Execute a read-only SELECT query against the StockPulse Postgres database.

    Use this tool for questions about products, orders, revenue, stock levels,
    customers, quantities, dates, totals, rankings, or any structured
    transactional data.

    Args:
        sql: A read-only SELECT statement. Do NOT include DML or DDL.

    Returns:
        A JSON-serialised list of row dicts, or a REFUSED/SQL ERROR string.
    """
    # --- Validation ---
    refusal = _validate_sql(sql)
    if refusal:
        return refusal

    # --- Limit injection ---
    safe_sql = _inject_limit(sql)

    # --- Execution ---
    conn = None
    try:
        conn = psycopg2.connect(
            settings.postgres_url,
            cursor_factory=psycopg2.extras.RealDictCursor,
        )
        with conn.cursor() as cur:
            # Enforce statement timeout
            cur.execute(
                f"SET LOCAL statement_timeout = {settings.sql_timeout_ms}"
            )
            cur.execute(safe_sql)
            return _rows_to_json(cur)

    except psycopg2.errors.QueryCanceled:
        return "SQL ERROR: statement timeout exceeded (5 s limit)"
    except psycopg2.Error as exc:
        return f"SQL ERROR: {exc.pgerror or str(exc)}"
    finally:
        if conn:
            conn.close()
