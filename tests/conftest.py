"""Pytest configuration and fixtures."""

import asyncio
from typing import AsyncGenerator, Generator

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.config import Settings


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create an event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def test_settings() -> Settings:
    """Test settings with mock values."""
    return Settings(
        database_url="postgresql://test:test@localhost:5432/test",
        redis_url=None,  # Use in-memory cache for tests
        openai_api_key=None,  # Disable OpenAI for tests
        debug=True,
    )


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """Create async test client."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.fixture
def sample_question() -> str:
    """Sample question for testing."""
    return "What are the symptoms of endometriosis?"


@pytest.fixture
def sample_sources() -> list:
    """Sample sources for testing."""
    return [
        {
            "source": "who",
            "title": "Endometriosis Fact Sheet",
            "content": "Endometriosis is a disease where tissue similar to the lining of the uterus grows outside the uterus.",
            "url": "https://www.who.int/news-room/fact-sheets/detail/endometriosis",
            "organization": "World Health Organization",
        },
        {
            "source": "pubmed",
            "title": "Clinical manifestations of endometriosis",
            "content": "Common symptoms include pelvic pain, painful periods, and infertility.",
            "url": "https://pubmed.ncbi.nlm.nih.gov/12345/",
            "organization": "PubMed/NCBI",
        },
    ]
