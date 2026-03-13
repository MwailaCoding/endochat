"""Tests for chat API endpoints."""

import pytest
from httpx import AsyncClient


class TestChatEndpoints:
    """Tests for /api/chat endpoints."""

    @pytest.mark.asyncio
    async def test_chat_starters(self, client: AsyncClient):
        """Test getting starter questions."""
        response = await client.get("/api/chat/starters")
        assert response.status_code == 200
        data = response.json()
        assert "questions" in data
        assert len(data["questions"]) > 0

    @pytest.mark.asyncio
    async def test_chat_suggestions(self, client: AsyncClient, sample_question: str):
        """Test getting suggestions for a question."""
        response = await client.get(
            "/api/chat/suggestions",
            params={"question": sample_question},
        )
        assert response.status_code == 200
        data = response.json()
        assert "suggestions" in data

    @pytest.mark.asyncio
    async def test_chat_validation(self, client: AsyncClient):
        """Test chat request validation."""
        # Empty question should fail
        response = await client.post(
            "/api/chat",
            json={"question": ""},
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_chat_question_too_long(self, client: AsyncClient):
        """Test chat rejects questions that are too long."""
        long_question = "What is endometriosis? " * 50  # Over 500 chars
        response = await client.post(
            "/api/chat",
            json={"question": long_question},
        )
        assert response.status_code == 422
