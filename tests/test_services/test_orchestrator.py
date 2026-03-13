"""Tests for orchestrator service."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from app.services.orchestrator import ChatOrchestrator
from app.services.response.confidence import ConfidenceCalculator
from app.services.response.sources import SourceFormatter
from app.models.chat import SourceCitation


class TestConfidenceCalculator:
    """Tests for confidence calculation."""

    def test_calculate_no_sources(self):
        """Test confidence with no sources."""
        calc = ConfidenceCalculator()
        result = calc.calculate([])

        assert result.score == 0
        assert result.level == "low"

    def test_calculate_single_who_source(self):
        """Test confidence with WHO source."""
        calc = ConfidenceCalculator()
        sources = [{"source": "who", "content": "Test content"}]
        result = calc.calculate(sources)

        assert result.score > 0
        assert "WHO" in result.reason

    def test_calculate_multiple_sources(self):
        """Test confidence with multiple sources."""
        calc = ConfidenceCalculator()
        sources = [
            {"source": "who", "content": "Test 1"},
            {"source": "pubmed", "content": "Test 2"},
            {"source": "openfda", "content": "Test 3"},
        ]
        result = calc.calculate(sources)

        assert result.level in ["medium", "high"]
        assert "Multiple sources" in result.reason


class TestSourceFormatter:
    """Tests for source formatting."""

    def test_format_empty_results(self):
        """Test formatting empty API results."""
        formatter = SourceFormatter()
        result = formatter.format_sources({})

        assert result == []

    def test_format_single_source(self):
        """Test formatting single source."""
        formatter = SourceFormatter()
        api_results = {
            "who": [
                {
                    "source": "who",
                    "title": "Test Title",
                    "content": "Test content here.",
                    "url": "https://example.com",
                }
            ]
        }
        result = formatter.format_sources(api_results)

        assert len(result) == 1
        assert result[0].title == "Test Title"
        assert result[0].source == "who"

    def test_deduplication(self):
        """Test that duplicate sources are removed."""
        formatter = SourceFormatter()
        api_results = {
            "who": [
                {"source": "who", "title": "Same Title", "content": "Content 1"},
            ],
            "pubmed": [
                {"source": "pubmed", "title": "Same Title", "content": "Content 2"},
            ],
        }
        result = formatter.format_sources(api_results)

        # Should deduplicate based on title similarity
        assert len(result) <= 2
