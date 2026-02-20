"""Pytest configuration and shared fixtures."""
import pytest
import os
from langchain_core.messages import HumanMessage, AIMessage

# Set a dummy GEMINI_API_KEY for testing if not already set
if "GEMINI_API_KEY" not in os.environ:
    os.environ["GEMINI_API_KEY"] = "test-key-for-testing"


@pytest.fixture
def sample_human_message():
    """Fixture providing a sample human message."""
    return HumanMessage(content="What is machine learning?")


@pytest.fixture
def sample_ai_message():
    """Fixture providing a sample AI message."""
    return AIMessage(content="Machine learning is a subset of AI...")


@pytest.fixture
def sample_conversation():
    """Fixture providing a sample conversation with multiple messages."""
    return [
        HumanMessage(content="What is Python?"),
        AIMessage(content="Python is a programming language."),
        HumanMessage(content="Tell me more about its features."),
        AIMessage(content="Python features include simplicity, readability, etc."),
    ]


@pytest.fixture
def sample_urls():
    """Fixture providing sample URLs to resolve."""
    class MockWebResult:
        def __init__(self, uri):
            self.web = type("Web", (), {"uri": uri})()

    return [
        MockWebResult("https://example.com/page1"),
        MockWebResult("https://example.com/page2"),
        MockWebResult("https://example.com/page1"),  # Duplicate
    ]
