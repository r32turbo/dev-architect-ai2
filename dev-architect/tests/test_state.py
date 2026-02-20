"""Unit tests for the state module."""
import pytest
from src.agent.state import (
    OverallState,
    ReflectionState,
    Query,
    QueryGenerationState,
    WebSearchState,
    SearchStateOutput,
)


class TestQueryClass:
    """Tests for the Query TypedDict."""

    def test_query_creation(self):
        """Test creating a Query object."""
        query: Query = {"query": "What is AI?", "rationale": "To understand AI basics"}
        assert query["query"] == "What is AI?"
        assert query["rationale"] == "To understand AI basics"

    def test_query_with_special_characters(self):
        """Test Query with special characters."""
        query: Query = {
            "query": "What's the difference between AI & ML?",
            "rationale": "Need to compare 'AI' vs. 'ML'",
        }
        assert "AI & ML" in query["query"]
        assert "'" in query["rationale"]


class TestSearchStateOutput:
    """Tests for the SearchStateOutput dataclass."""

    def test_default_initialization(self):
        """Test creating SearchStateOutput with default values."""
        output = SearchStateOutput()
        assert output.running_summary is None

    def test_initialization_with_summary(self):
        """Test creating SearchStateOutput with a summary."""
        summary_text = "This is a comprehensive research summary..."
        output = SearchStateOutput(running_summary=summary_text)
        assert output.running_summary == summary_text

    def test_output_serialization(self):
        """Test that SearchStateOutput can be converted to dict."""
        output = SearchStateOutput(running_summary="Test summary")
        # Convert to dict for verification
        output_dict = {
            "running_summary": output.running_summary,
        }
        assert output_dict["running_summary"] == "Test summary"

    def test_long_summary(self):
        """Test SearchStateOutput with a long summary text."""
        long_text = "A" * 10000  # 10,000 character string
        output = SearchStateOutput(running_summary=long_text)
        assert len(output.running_summary) == 10000
        assert output.running_summary == long_text


class TestWebSearchState:
    """Tests for the WebSearchState TypedDict."""

    def test_web_search_state_creation(self):
        """Test creating a WebSearchState object."""
        state: WebSearchState = {
            "search_query": "Python programming tutorials",
            "id": "search_001",
        }
        assert state["search_query"] == "Python programming tutorials"
        assert state["id"] == "search_001"

    def test_web_search_state_with_numbers(self):
        """Test WebSearchState with numeric IDs."""
        state: WebSearchState = {"search_query": "Latest AI breakthroughs", "id": "12345"}
        assert state["id"] == "12345"


class TestQueryGenerationState:
    """Tests for the QueryGenerationState TypedDict."""

    def test_query_generation_state_creation(self):
        """Test creating QueryGenerationState with queries."""
        state: QueryGenerationState = {
            "search_query": [
                {"query": "Query 1", "rationale": "Rationale 1"},
                {"query": "Query 2", "rationale": "Rationale 2"},
            ]
        }
        assert len(state["search_query"]) == 2
        assert state["search_query"][0]["query"] == "Query 1"

    def test_query_generation_state_empty(self):
        """Test QueryGenerationState with empty query list."""
        state: QueryGenerationState = {"search_query": []}
        assert state["search_query"] == []


class TestReflectionState:
    """Tests for the ReflectionState TypedDict."""

    def test_reflection_state_sufficient(self):
        """Test ReflectionState when sufficient information is gathered."""
        state: ReflectionState = {
            "is_sufficient": True,
            "knowledge_gap": "",
            "follow_up_queries": [],
            "research_loop_count": 2,
            "number_of_ran_queries": 5,
        }
        assert state["is_sufficient"] is True
        assert state["knowledge_gap"] == ""
        assert len(state["follow_up_queries"]) == 0

    def test_reflection_state_insufficient(self):
        """Test ReflectionState when more research is needed."""
        state: ReflectionState = {
            "is_sufficient": False,
            "knowledge_gap": "Need more details on specific implementations",
            "follow_up_queries": ["Follow-up query 1", "Follow-up query 2"],
            "research_loop_count": 1,
            "number_of_ran_queries": 3,
        }
        assert state["is_sufficient"] is False
        assert "implementations" in state["knowledge_gap"]
        assert len(state["follow_up_queries"]) == 2

    def test_reflection_state_loop_tracking(self):
        """Test that loop counts are tracked correctly."""
        state: ReflectionState = {
            "is_sufficient": False,
            "knowledge_gap": "More research needed",
            "follow_up_queries": [],
            "research_loop_count": 5,
            "number_of_ran_queries": 15,
        }
        assert state["research_loop_count"] == 5
        assert state["number_of_ran_queries"] == 15


class TestOverallState:
    """Tests for the OverallState TypedDict."""

    def test_overall_state_initialization(self):
        """Test initializing OverallState with basic values."""
        state: OverallState = {
            "messages": [],
            "search_query": [],
            "web_research_result": [],
            "sources_gathered": [],
            "initial_search_query_count": 3,
            "max_research_loops": 5,
            "research_loop_count": 0,
            "reasoning_model": "gemini-pro",
        }
        assert state["initial_search_query_count"] == 3
        assert state["max_research_loops"] == 5
        assert state["reasoning_model"] == "gemini-pro"

    def test_overall_state_with_data(self):
        """Test OverallState with populated data."""
        from langchain_core.messages import HumanMessage

        msg = HumanMessage(content="Research this topic")
        state: OverallState = {
            "messages": [msg],
            "search_query": ["Query 1", "Query 2"],
            "web_research_result": ["Result 1", "Result 2"],
            "sources_gathered": ["Source 1"],
            "initial_search_query_count": 2,
            "max_research_loops": 3,
            "research_loop_count": 1,
            "reasoning_model": "gemini-pro",
        }
        assert len(state["messages"]) == 1
        assert len(state["search_query"]) == 2
        assert len(state["web_research_result"]) == 2

    def test_overall_state_model_names(self):
        """Test OverallState with different model names."""
        for model_name in ["gemini-pro", "gemini-ultra", "gpt-4", "claude-3"]:
            state: OverallState = {
                "messages": [],
                "search_query": [],
                "web_research_result": [],
                "sources_gathered": [],
                "initial_search_query_count": 1,
                "max_research_loops": 1,
                "research_loop_count": 0,
                "reasoning_model": model_name,
            }
            assert state["reasoning_model"] == model_name
