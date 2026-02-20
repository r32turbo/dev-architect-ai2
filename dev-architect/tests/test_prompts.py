"""Unit tests for the prompts module."""
import pytest
from src.agent.prompts import (
    query_writer_instructions,
    web_searcher_instructions,
    reflection_instructions,
    answer_instructions,
    get_current_date,
)


class TestPromptFunctions:
    """Tests for prompt template functions."""

    def test_get_current_date_returns_string(self):
        """Test that get_current_date returns a string."""
        date = get_current_date()
        assert isinstance(date, str)
        assert len(date) > 0

    def test_get_current_date_format(self):
        """Test that get_current_date returns correct format."""
        date = get_current_date()
        # Should contain month, day, and year
        import re

        pattern = r"\w+ \d{1,2}, \d{4}"
        assert re.match(pattern, date) is not None


class TestPromptTemplates:
    """Tests for prompt templates."""

    def test_query_writer_instructions_exists(self):
        """Test that query_writer_instructions is defined."""
        assert query_writer_instructions is not None
        assert isinstance(query_writer_instructions, str)

    def test_query_writer_instructions_not_empty(self):
        """Test that query_writer_instructions is not empty."""
        assert len(query_writer_instructions) > 0

    def test_query_writer_instructions_contains_keywords(self):
        """Test that query_writer_instructions contains expected keywords."""
        text_lower = query_writer_instructions.lower()
        assert "query" in text_lower or "search" in text_lower
        assert "json" in text_lower

    def test_web_searcher_instructions_exists(self):
        """Test that web_searcher_instructions is defined."""
        assert web_searcher_instructions is not None
        assert isinstance(web_searcher_instructions, str)

    def test_web_searcher_instructions_not_empty(self):
        """Test that web_searcher_instructions is not empty."""
        assert len(web_searcher_instructions) > 0

    def test_web_searcher_instructions_contains_keywords(self):
        """Test that web_searcher_instructions contains expected keywords."""
        text_lower = web_searcher_instructions.lower()
        assert "search" in text_lower
        assert "research" in text_lower or "information" in text_lower

    def test_reflection_instructions_exists(self):
        """Test that reflection_instructions is defined."""
        assert reflection_instructions is not None
        assert isinstance(reflection_instructions, str)

    def test_reflection_instructions_not_empty(self):
        """Test that reflection_instructions is not empty."""
        assert len(reflection_instructions) > 0

    def test_reflection_instructions_contains_keywords(self):
        """Test that reflection_instructions contains expected keywords."""
        text_lower = reflection_instructions.lower()
        assert "gap" in text_lower or "sufficient" in text_lower
        assert "json" in text_lower

    def test_answer_instructions_exists(self):
        """Test that answer_instructions is defined."""
        assert answer_instructions is not None
        assert isinstance(answer_instructions, str)

    def test_answer_instructions_not_empty(self):
        """Test that answer_instructions is not empty."""
        assert len(answer_instructions) > 0

    def test_answer_instructions_contains_keywords(self):
        """Test that answer_instructions contains expected keywords."""
        text_lower = answer_instructions.lower()
        assert "answer" in text_lower
        assert "source" in text_lower or "summary" in text_lower


class TestPromptPlaceholders:
    """Tests for prompt placeholder functionality."""

    def test_query_writer_has_placeholders(self):
        """Test that query_writer_instructions has format placeholders."""
        # Should have placeholders like {number_queries}, {current_date}, {research_topic}
        assert "{" in query_writer_instructions
        assert "}" in query_writer_instructions

    def test_web_searcher_has_placeholders(self):
        """Test that web_searcher_instructions has format placeholders."""
        assert "{" in web_searcher_instructions
        assert "}" in web_searcher_instructions

    def test_reflection_has_placeholders(self):
        """Test that reflection_instructions has format placeholders."""
        assert "{" in reflection_instructions
        assert "}" in reflection_instructions

    def test_answer_has_placeholders(self):
        """Test that answer_instructions has format placeholders."""
        assert "{" in answer_instructions
        assert "}" in answer_instructions

    def test_query_writer_can_format(self):
        """Test that query_writer_instructions can be formatted."""
        formatted = query_writer_instructions.format(
            number_queries=3,
            current_date="January 1, 2024",
            research_topic="Python programming",
        )
        assert "Python programming" in formatted
        assert "January 1, 2024" in formatted

    def test_web_searcher_can_format(self):
        """Test that web_searcher_instructions can be formatted."""
        formatted = web_searcher_instructions.format(
            research_topic="AI applications",
            current_date="January 1, 2024",
        )
        assert "AI applications" in formatted

    def test_reflection_can_format(self):
        """Test that reflection_instructions can be formatted."""
        formatted = reflection_instructions.format(
            research_topic="Cloud computing",
            summaries="Summary of cloud computing information",
        )
        assert "Cloud computing" in formatted

    def test_answer_can_format(self):
        """Test that answer_instructions can be formatted."""
        formatted = answer_instructions.format(
            current_date="January 1, 2024",
            research_topic="Machine Learning",
            summaries="ML model summary",
        )
        assert "Machine Learning" in formatted
