"""
conftest.py — Shared pytest fixtures for all test levels.
"""

import os

import pytest
from dotenv import load_dotenv

# Load .env for integration and e2e tests
load_dotenv()


@pytest.fixture(scope="session")
def postgres_url() -> str:
    url = os.environ.get("POSTGRES_URL")
    if not url:
        pytest.skip("POSTGRES_URL not set — skipping integration test")
    return url


@pytest.fixture(scope="session")
def mongo_url() -> str:
    url = os.environ.get("MONGO_URL")
    if not url:
        pytest.skip("MONGO_URL not set — skipping integration test")
    return url


@pytest.fixture(scope="session")
def openai_api_key() -> str:
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        pytest.skip("OPENAI_API_KEY not set — skipping test requiring LLM")
    return key
