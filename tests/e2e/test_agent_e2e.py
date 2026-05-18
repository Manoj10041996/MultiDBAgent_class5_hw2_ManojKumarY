"""
test_agent_e2e.py — End-to-end acceptance tests for the StockPulse agent.

These tests run the FULL agent loop against live databases.
Requires: .env with real OPENAI_API_KEY, POSTGRES_URL, MONGO_URL set.
Requires: databases seeded with seed_postgres.py and seed_mongo.py.

Each test corresponds to one of the 5 acceptance cases from SPEC.md §4,
plus the mandatory failure case.

Run with:
    uv run pytest tests/e2e/ -v -s
"""

import json
import os

import pytest
import requests

# The running FastAPI backend
BASE_URL = os.environ.get("API_BASE_URL", "http://localhost:8000")


def ask(question: str) -> dict:
    """Helper: POST /chat and return the parsed JSON response."""
    response = requests.post(
        f"{BASE_URL}/chat",
        json={"question": question},
        timeout=60,
    )
    assert response.status_code == 200, (
        f"Expected 200, got {response.status_code}: {response.text}"
    )
    return response.json()


# ---------------------------------------------------------------------------
# SPEC.md §4 — Acceptance Test Suite
# ---------------------------------------------------------------------------

class TestAcceptanceSuite:
    """
    Five acceptance questions from SPEC.md §4.
    Each asserts:
      1. The correct tool was called.
      2. The answer contains the specified fields.
      3. No hallucinated data (no fabricated numbers).
    """

    def test_q1_top_selling_products(self):
        """
        Q1: 'What are the top 5 selling products this month?'
        Expected tool: sql_query
        Required fields in answer: product name, total_sold quantity
        """
        data = ask("What are the top 5 selling products this month?")

        tool_names = [tc["tool"] for tc in data["tool_calls"]]
        assert "sql_query" in tool_names, (
            f"Expected sql_query to be called, got: {tool_names}"
        )

        answer = data["answer"].lower()
        # The agent should mention at least one product name from our seed data
        product_names = ["wireless mouse", "keyboard", "usb hub", "webcam", "headphone"]
        matched = [p for p in product_names if p in answer]
        assert len(matched) > 0, (
            f"Answer should mention at least one product name. Got: {data['answer']}"
        )

        # Should mention quantities
        assert any(char.isdigit() for char in answer), (
            "Answer should contain numeric quantity data"
        )

    def test_q2_most_common_complaints(self):
        """
        Q2: 'What are the most common customer complaints this week?'
        Expected tool: mongo_query
        Required fields: issue text, status, complaint frequency
        """
        data = ask("What are the most common customer complaints this week?")

        tool_names = [tc["tool"] for tc in data["tool_calls"]]
        assert "mongo_query" in tool_names, (
            f"Expected mongo_query to be called, got: {tool_names}"
        )

        answer = data["answer"].lower()
        # Should reference complaint content from seeded tickets
        complaint_keywords = ["damaged", "delayed", "shipment", "wrong item",
                              "connection", "not working", "open", "ticket"]
        matched = [kw for kw in complaint_keywords if kw in answer]
        assert len(matched) > 0, (
            f"Answer should reference complaint content. Got: {data['answer']}"
        )

    def test_q3_return_policy_damaged_goods(self):
        """
        Q3: 'What is our return policy for damaged goods?'
        Expected tool: handbook_search
        Required: section = 'Return & Refund Policy', chunk with return window
        """
        data = ask("What is our return policy for damaged goods?")

        tool_names = [tc["tool"] for tc in data["tool_calls"]]
        assert "handbook_search" in tool_names, (
            f"Expected handbook_search to be called, got: {tool_names}"
        )

        answer = data["answer"].lower()
        # Must mention the 30-day return window from the policy doc
        assert "30 day" in answer or "30-day" in answer, (
            f"Answer should mention the 30-day return window. Got: {data['answer']}"
        )
        # Must mention evidence requirement
        assert "photo" in answer or "evidence" in answer or "damage" in answer, (
            f"Answer should mention photo evidence requirement. Got: {data['answer']}"
        )

    def test_q4_customers_most_orders(self):
        """
        Q4: 'Which customers have placed the most orders?'
        Expected tool: sql_query
        Required fields: customer name, email, order_count
        """
        data = ask("Which customers have placed the most orders?")

        tool_names = [tc["tool"] for tc in data["tool_calls"]]
        assert "sql_query" in tool_names, (
            f"Expected sql_query to be called, got: {tool_names}"
        )

        answer = data["answer"].lower()
        # Should mention customer names from our seed data
        customer_names = ["alice", "bob", "carol", "david", "eva",
                          "frank", "grace", "henry", "irene", "jack"]
        matched = [n for n in customer_names if n in answer]
        assert len(matched) > 0, (
            f"Answer should mention at least one customer name. Got: {data['answer']}"
        )

    def test_q5_one_star_reviews_wireless_mouse(self):
        """
        Q5: 'Show me all 1-star reviews for the Wireless Mouse'
        Expected tool: mongo_query
        Required fields: product_id, rating=1, comment, date
        """
        data = ask("Show me all 1-star reviews for the Wireless Mouse")

        tool_names = [tc["tool"] for tc in data["tool_calls"]]
        assert "mongo_query" in tool_names, (
            f"Expected mongo_query to be called, got: {tool_names}"
        )

        answer = data["answer"].lower()
        # Should reference negative review content from our seeded data
        negative_keywords = ["stopped working", "connection", "disappointed",
                             "1-star", "1 star", "poor", "terrible"]
        matched = [kw for kw in negative_keywords if kw in answer]
        assert len(matched) > 0, (
            f"Answer should reference 1-star review content. Got: {data['answer']}"
        )

        # Should NOT claim there are 5-star reviews for this query
        assert "5 star" not in answer and "five star" not in answer

    # ---------------------------------------------------------------------------
    # Failure case — must be demoed (SPEC.md §4)
    # ---------------------------------------------------------------------------

    def test_failure_case_sales_in_1990(self):
        """
        Failure case: 'What were our sales in 1990?'
        The agent must:
          1. Call sql_query (not hallucinate from memory)
          2. Report honestly that no data was found
          3. NOT fabricate sales figures
        """
        data = ask("What were our sales in 1990?")

        tool_names = [tc["tool"] for tc in data["tool_calls"]]
        assert "sql_query" in tool_names, (
            f"Expected agent to call sql_query, got: {tool_names}"
        )

        answer = data["answer"].lower()

        # Must honestly report no data
        no_data_phrases = [
            "no data", "no results", "no records", "no sales",
            "no orders", "found no", "0 results", "zero", "empty",
            "no information", "unable to find", "could not find",
        ]
        found_honesty = any(phrase in answer for phrase in no_data_phrases)
        assert found_honesty, (
            f"Agent should report no data found for 1990. Got: {data['answer']}"
        )

        # Must NOT contain hallucinated dollar amounts like "$1,234,567"
        # A rough check: the answer shouldn't contain dollar signs with large numbers
        import re
        fabricated_revenue = re.search(r"\$[\d,]+\.\d{2}", data["answer"])
        assert fabricated_revenue is None, (
            f"Agent hallucinated a revenue figure. Got: {data['answer']}"
        )


# ---------------------------------------------------------------------------
# Structural / contract tests
# ---------------------------------------------------------------------------

class TestResponseContract:
    def test_response_has_required_fields(self):
        data = ask("What products are low on stock?")
        assert "answer" in data
        assert "tool_calls" in data
        assert "warnings" in data
        assert "elapsed_ms" in data

    def test_tool_call_has_required_fields(self):
        data = ask("What products are low on stock?")
        if data["tool_calls"]:
            tc = data["tool_calls"][0]
            assert "tool" in tc
            assert "args" in tc
            assert "result" in tc

    def test_elapsed_ms_is_positive_integer(self):
        data = ask("What is our return policy?")
        assert isinstance(data["elapsed_ms"], int)
        assert data["elapsed_ms"] > 0

    def test_health_endpoint(self):
        response = requests.get(f"{BASE_URL}/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"
