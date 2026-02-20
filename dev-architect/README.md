# Course Architect - LangGraph Research Agent

A sophisticated LangGraph-powered research agent that leverages Google's Gemini AI models to perform comprehensive web research, analyze findings, and generate well-cited answers.

## Overview

The Course Architect backend is an intelligent research agent designed to answer complex questions by:

1. **Generating optimized search queries** - Creates diverse and targeted web search queries based on your research topic
2. **Conducting web research** - Performs searches using the native Google Search API
3. **Reflecting on findings** - Analyzes gathered information to identify knowledge gaps
4. **Iterative refinement** - Automatically generates follow-up queries to fill gaps
5. **Synthesizing answers** - Produces comprehensive, well-cited answers with source attribution

## Features

- 🧠 **AI-Powered Query Generation** - Uses Gemini models to create intelligent search queries
- 🔍 **Automated Web Research** - Integrates with Google Search API for real-time information
- 💡 **Reflective Analysis** - Intelligently identifies missing information and refines searches
- 📝 **Citation Management** - Automatically tracks and formats citations from sources
- 🔄 **Iterative Research Loops** - Configurable maximum loops for comprehensive research
- ⚙️ **Flexible Configuration** - Customizable LLM models, query counts, and research depth
- 🚀 **FastAPI Backend** - Production-ready REST API for easy integration
- 📦 **Type-Safe** - Full type hints and Pydantic validation throughout

## Installation

### Prerequisites

- Python 3.11 or higher
- `GEMINI_API_KEY` environment variable set with your Google Gemini API key

### Setup

1. Clone the repository and navigate to the project directory:
```bash
cd course-architect
```

2. Install the project in editable mode:
```bash
uv pip install -e .
```

Or with pip:
```bash
pip install -e .
```

3. Install development dependencies (including pytest):
```bash
uv pip install -e ".[dev]"
```

## Configuration

### Environment Variables

Create a `.env` file in the project root with your API key:

```bash
GEMINI_API_KEY=your_actual_api_key_here
```

### Configuration Options

The agent behavior can be customized through the `Configuration` class:

- `query_generator_model` - LLM model for query generation (default: `gemini-2.5-pro-preview-05-06`)
- `reflection_model` - LLM model for reflection analysis (default: `gemini-2.5-pro-preview-05-06`)
- `answer_model` - LLM model for final answer generation (default: `gemini-2.5-pro-preview-05-06`)
- `number_of_initial_queries` - Initial search query count (default: 3)
- `max_research_loops` - Maximum reflection/refinement loops (default: 2)

## Usage

### Command Line Interface

Run the research agent from the command line:

```bash
python examples/cli_research.py "Your research question here"
```

#### CLI Options

```bash
python examples/cli_research.py "What are the latest advances in AI?" \
  --initial-queries 4 \
  --max-loops 3 \
  --reasoning-model gemini-2.5-pro-preview-05-06
```

- `question` - Your research question (required)
- `--initial-queries` - Number of initial search queries (default: 3)
- `--max-loops` - Maximum research loops (default: 2)
- `--reasoning-model` - Model for final answer (default: gemini-2.5-pro-preview-05-06)

### Programmatic Usage

```python
from langchain_core.messages import HumanMessage
from agent.graph import graph

state = {
    "messages": [HumanMessage(content="Your research question")],
    "initial_search_query_count": 3,
    "max_research_loops": 2,
    "reasoning_model": "gemini-2.5-pro-preview-05-06",
}

result = graph.invoke(state)
answer = result["messages"][-1].content
print(answer)
```

### FastAPI Backend

The project includes a FastAPI application for serving the agent:

```bash
uvicorn src.agent.app:app --reload
```

The frontend will be served at `http://localhost:8000/app`

## Project Structure

```
course-architect/
├── src/agent/
│   ├── app.py                    # FastAPI application
│   ├── graph.py                  # LangGraph agent definition
│   ├── state.py                  # State management TypedDicts
│   ├── configuration.py          # Configuration settings
│   ├── prompts.py                # LLM prompt templates
│   ├── utils.py                  # Utility functions
│   ├── tools_and_schemas.py      # Tool definitions and schemas
│   └── __init__.py
├── tests/
│   ├── test_utils.py             # Utility function tests
│   ├── test_state.py             # State management tests
│   ├── test_configuration.py     # Configuration tests
│   ├── test_prompts.py           # Prompt template tests
│   ├── test_app.py               # FastAPI app tests
│   ├── conftest.py               # Shared pytest fixtures
│   └── README.md                 # Testing documentation
├── examples/
│   └── cli_research.py           # Command-line interface example
├── pyproject.toml                # Project metadata and dependencies
├── pytest.ini                    # Pytest configuration
└── README.md                     # This file
```

## Architecture

### Graph Workflow

The research agent uses a LangGraph state machine with the following workflow:

```
START
  ↓
generate_query: Generate search queries
  ↓
continue_to_web_research: Route to parallel web research
  ↓
web_research (parallel): Perform web searches
  ↓
reflection: Analyze findings and identify gaps
  ↓
[Decision: Research sufficient?]
  ├─ Yes → generate_answer: Create final answer
  │         ↓
  │         END
  └─ No → generate_query: Generate new queries (loop)
```

### Key Components

- **Query Generator** - Generates optimized search queries using Gemini
- **Web Researcher** - Executes searches and synthesizes findings
- **Reflector** - Analyzes results to identify knowledge gaps
- **Answer Generator** - Produces final answer with citations
- **State Management** - Tracks messages, searches, findings, and sources

## Testing

The project includes comprehensive unit tests using pytest.

### Run All Tests

```bash
pytest tests/ -v
```

### Run Specific Test File

```bash
pytest tests/test_utils.py -v
```

### Run Specific Test

```bash
pytest tests/test_utils.py::TestGetResearchTopic::test_single_message -v
```

### Generate Coverage Report

```bash
pytest tests/ --cov=src --cov-report=html
```

### Test Statistics

- **72 unit tests** covering all core components
- Tests for utility functions, state management, configuration, prompts, and FastAPI routes
- Shared fixtures for common test patterns

For more testing details, see [tests/README.md](tests/README.md)

## Development

### Code Quality

The project uses the following tools for code quality:

- **ruff** - Fast Python linter
- **mypy** - Static type checker
- **pytest** - Testing framework

### Install Development Dependencies

```bash
uv pip install -e ".[dev]"
```

### Run Linting

```bash
ruff check src/ tests/
```

### Run Type Checking

```bash
mypy src/
```

### Format Code

```bash
ruff format src/ tests/
```

## Dependencies

### Core Dependencies

- `langgraph` - Graph-based orchestration framework
- `langchain` - LLM framework
- `langchain-google-genai` - Google Gemini integration
- `google-genai` - Google Gemini SDK
- `fastapi` - Web framework
- `python-dotenv` - Environment variable management

### Development Dependencies

- `pytest` - Testing framework
- `pytest-asyncio` - Async test support
- `mypy` - Type checking
- `ruff` - Linting and formatting

## License

MIT License - See LICENSE file for details

## Support

For issues and questions:
- Check the [tests/README.md](tests/README.md) for testing examples
- Review example usage in [examples/cli_research.py](examples/cli_research.py)
- Examine the prompt templates in [src/agent/prompts.py](src/agent/prompts.py)

## Author

Created by Philipp Schmid - [philipp@huggingface.co](mailto:schmidphilipp1995@gmail.com)
