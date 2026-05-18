"""
test_rag_tool.py — Unit tests for the handbook_search tool.

All OpenAI API calls and Postgres connections are mocked. Tests cover:
  - Good input (valid query, returns chunks)
  - Empty query returns empty list
  - k > 5 silently capped to 5
  - Embedding API failure returns SEARCH ERROR string
  - Vector search DB failure returns SEARCH ERROR string
  - Results below similarity threshold are filtered out
"""

from unittest.mock import MagicMock, patch

import pytest

from backend.tools.rag_tool import handbook_search


# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------

def _make_mock_embedding(dimension: int = 1536) -> list[float]:
    return [0.01] * dimension


def _patch_embed_and_db(mock_results: list[dict]):
    """
    Returns a context manager that patches both _embed and _vector_search.
    mock_results: list of dicts with {section, chunk, similarity}
    """
    embed_patch = patch(
        "backend.tools.rag_tool._embed",
        return_value=_make_mock_embedding(),
    )
    search_patch = patch(
        "backend.tools.rag_tool._vector_search",
        return_value=mock_results,
    )
    return embed_patch, search_patch


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestHandbookSearch:
    def test_good_query_returns_chunks(self):
        mock_results = [
            {"section": "Return & Refund Policy", "chunk": "Damaged goods may be returned within 30 days.", "similarity": 0.85},
            {"section": "Return & Refund Policy", "chunk": "Refunds processed within 5-7 business days.", "similarity": 0.80},
        ]
        ep, sp = _patch_embed_and_db(mock_results)
        with ep, sp:
            result = handbook_search.invoke({"query": "return policy for damaged goods"})

        assert "Return & Refund Policy" in result
        assert "30 days" in result

    def test_empty_query_returns_empty_list(self):
        result = handbook_search.invoke({"query": ""})
        assert result == "[]"

    def test_whitespace_only_query_returns_empty_list(self):
        result = handbook_search.invoke({"query": "   "})
        assert result == "[]"

    def test_k_capped_at_5(self):
        """k=10 must be silently capped to 5."""
        mock_results = [
            {"section": "Shipping Policy", "chunk": "Free shipping over $50.", "similarity": 0.9},
        ]
        ep, sp = _patch_embed_and_db(mock_results)
        with ep, sp as mock_search:
            handbook_search.invoke({"query": "shipping", "k": 10})
            # _vector_search must have been called with k <= 5
            call_k = mock_search.call_args[0][1]
            assert call_k <= 5

    def test_embedding_failure_returns_search_error(self):
        with patch("backend.tools.rag_tool._embed", side_effect=Exception("API timeout")):
            result = handbook_search.invoke({"query": "return policy"})

        assert result.startswith("SEARCH ERROR")
        assert "embedding failed" in result.lower()

    def test_vector_search_failure_returns_search_error(self):
        with patch("backend.tools.rag_tool._embed", return_value=_make_mock_embedding()):
            with patch("backend.tools.rag_tool._vector_search", side_effect=Exception("pgvector error")):
                result = handbook_search.invoke({"query": "return policy"})

        assert result.startswith("SEARCH ERROR")
        assert "vector search failed" in result.lower()

    def test_low_similarity_results_filtered_out(self):
        """Results below threshold (0.2) should not appear in output."""
        mock_results = [
            {"section": "Discount Policy", "chunk": "Bulk orders get 10% off.", "similarity": 0.05},  # below threshold
            {"section": "Shipping Policy", "chunk": "Free shipping on orders over $50.", "similarity": 0.01},
        ]
        ep, sp = _patch_embed_and_db(mock_results)
        with ep, sp:
            result = handbook_search.invoke({"query": "what is the return window"})

        # All results were below threshold, should return empty list
        assert result == "[]"

    def test_mixed_similarity_only_relevant_returned(self):
        """Only chunks above threshold should be returned."""
        mock_results = [
            {"section": "Return & Refund Policy", "chunk": "Returns accepted within 30 days.", "similarity": 0.88},
            {"section": "Unrelated Section", "chunk": "Some irrelevant content.", "similarity": 0.05},
        ]
        ep, sp = _patch_embed_and_db(mock_results)
        with ep, sp:
            result = handbook_search.invoke({"query": "return window"})

        assert "30 days" in result
        assert "irrelevant" not in result
