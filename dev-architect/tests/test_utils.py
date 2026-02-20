"""Unit tests for the utils module."""
import pytest
from langchain_core.messages import HumanMessage, AIMessage

from src.agent.utils import get_research_topic, resolve_urls


class TestGetResearchTopic:
    """Tests for the get_research_topic function."""

    def test_single_message(self, sample_human_message):
        """Test extracting research topic from a single message."""
        topic = get_research_topic([sample_human_message])
        assert topic == "What is machine learning?"
        assert isinstance(topic, str)

    def test_multiple_messages(self, sample_conversation):
        """Test extracting research topic from multiple messages."""
        topic = get_research_topic(sample_conversation)
        assert "What is Python?" in topic
        assert "Python is a programming language." in topic
        assert "User:" in topic
        assert "Assistant:" in topic

    def test_empty_message_list(self):
        """Test behavior with empty message list."""
        result = get_research_topic([])
        # Should return an empty string for empty message list
        assert result == ""
        assert isinstance(result, str)

    def test_human_message_only(self, sample_human_message):
        """Test with only human messages."""
        topic = get_research_topic([sample_human_message])
        assert "machine learning" in topic.lower()

    def test_ai_message_only(self, sample_ai_message):
        """Test with only AI messages."""
        topic = get_research_topic([sample_ai_message])
        assert "Machine learning" in topic

    def test_message_content_preservation(self):
        """Test that message content is preserved accurately."""
        messages = [
            HumanMessage(content="Explain quantum computing"),
            AIMessage(content="Quantum computing uses quantum bits..."),
        ]
        topic = get_research_topic(messages)
        assert "Explain quantum computing" in topic
        assert "Quantum computing uses quantum bits..." in topic

    def test_special_characters_in_messages(self):
        """Test handling of special characters in messages."""
        messages = [HumanMessage(content="What is AI? #important @urgent")]
        topic = get_research_topic(messages)
        assert "#important @urgent" in topic


class TestResolveUrls:
    """Tests for the resolve_urls function."""

    def test_basic_url_resolution(self, sample_urls):
        """Test basic URL resolution."""
        resolved = resolve_urls(sample_urls, id=1)
        assert isinstance(resolved, dict)
        assert len(resolved) <= len(sample_urls)  # Duplicates should be combined

    def test_url_mapping_consistency(self, sample_urls):
        """Test that identical URLs map to the same shortened URL."""
        resolved = resolve_urls(sample_urls, id=1)
        urls = [item.web.uri for item in sample_urls]
        
        # The first occurrence of a URL should be at index 0
        assert resolved[urls[0]] == "https://vertexaisearch.cloud.google.com/id/1-0"
        # The second occurrence (duplicate) should map to the same value
        assert resolved[urls[0]] == resolved[urls[2]]

    def test_unique_urls_get_unique_mapping(self):
        """Test that unique URLs get unique mappings."""
        class MockWebResult:
            def __init__(self, uri):
                self.web = type("Web", (), {"uri": uri})()

        urls = [
            MockWebResult("https://example.com/unique1"),
            MockWebResult("https://example.com/unique2"),
            MockWebResult("https://example.com/unique3"),
        ]
        
        resolved = resolve_urls(urls, id=42)
        assert len(resolved) == 3
        assert resolved["https://example.com/unique1"] == "https://vertexaisearch.cloud.google.com/id/42-0"
        assert resolved["https://example.com/unique2"] == "https://vertexaisearch.cloud.google.com/id/42-1"
        assert resolved["https://example.com/unique3"] == "https://vertexaisearch.cloud.google.com/id/42-2"

    def test_url_prefix_format(self, sample_urls):
        """Test that resolved URLs have the correct prefix."""
        resolved = resolve_urls(sample_urls, id=99)
        for shortened_url in resolved.values():
            assert shortened_url.startswith("https://vertexaisearch.cloud.google.com/id/99-")

    def test_different_id_produces_different_urls(self):
        """Test that different IDs produce different shortened URLs."""
        class MockWebResult:
            def __init__(self, uri):
                self.web = type("Web", (), {"uri": uri})()

        urls = [MockWebResult("https://example.com/test")]
        
        resolved1 = resolve_urls(urls, id=1)
        resolved2 = resolve_urls(urls, id=2)
        
        url = "https://example.com/test"
        assert resolved1[url] != resolved2[url]
        assert "1-0" in resolved1[url]
        assert "2-0" in resolved2[url]

    def test_empty_url_list(self):
        """Test with an empty URL list."""
        resolved = resolve_urls([], id=1)
        assert resolved == {}
