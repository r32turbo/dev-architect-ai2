# Unit Testing Guide

This directory contains unit tests for the course-architect agent project using pytest.

## Test Structure

The test suite is organized into the following files:

- **`test_utils.py`** - Tests for utility functions like `get_research_topic()` and `resolve_urls()`
- **`test_state.py`** - Tests for state management classes and TypedDicts
- **`test_configuration.py`** - Tests for the Configuration class
- **`test_prompts.py`** - Tests for prompt templates
- **`test_app.py`** - Tests for the FastAPI application and routing
- **`conftest.py`** - Shared fixtures used across test files

## Installation

First, install the development dependencies including pytest:

```bash
cd course-architect
pip install -e ".[dev]"
```

This will install:
- `pytest>=7.4.0` - Testing framework
- `pytest-asyncio>=0.21.0` - Support for async test functions

## Running Tests

### Run all tests:
```bash
pytest
```

### Run tests with verbose output:
```bash
pytest -v
```

### Run a specific test file:
```bash
pytest tests/test_utils.py
```

### Run a specific test class:
```bash
pytest tests/test_utils.py::TestGetResearchTopic
```

### Run a specific test:
```bash
pytest tests/test_utils.py::TestGetResearchTopic::test_single_message
```

### Run tests matching a pattern:
```bash
pytest -k "test_query" -v
```

### Run with coverage report:
```bash
pip install pytest-cov
pytest --cov=src --cov-report=html
```

## Test Categories

### Utility Tests (`test_utils.py`)
- Tests for message topic extraction
- Tests for URL resolution and mapping
- Edge case handling (empty inputs, duplicates, special characters)

### State Management Tests (`test_state.py`)
- Tests for TypedDict state classes
- Tests for SearchStateOutput dataclass
- Tests for state initialization and validation

### Configuration Tests (`test_configuration.py`)
- Tests for Configuration object creation
- Tests for configuration validation
- Tests for default values

### Prompt Tests (`test_prompts.py`)
- Tests for prompt template existence
- Tests for prompt content structure
- Tests for prompt variables and keywords

### Application Tests (`test_app.py`)
- Tests for FastAPI app initialization
- Tests for frontend router creation
- Tests for error handling

## Writing New Tests

### Example test structure:
```python
class TestNewFeature:
    """Tests for the new feature."""
    
    def test_basic_functionality(self):
        """Test basic functionality."""
        result = some_function()
        assert result is not None
    
    def test_with_fixture(self, sample_human_message):
        """Test using a fixture."""
        result = process_message(sample_human_message)
        assert result == expected_value
```

### Using fixtures:
Fixtures are defined in `conftest.py` and can be used in any test:

```python
def test_with_messages(self, sample_conversation):
    """Test with multiple messages."""
    topic = get_research_topic(sample_conversation)
    assert "Python" in topic
```

## Available Fixtures

- `sample_human_message` - A single HumanMessage
- `sample_ai_message` - A single AIMessage  
- `sample_conversation` - A list of multiple messages (human and AI)
- `sample_urls` - Mock web result objects with URLs

## Best Practices

1. **Use descriptive test names** - Test names should clearly describe what is being tested
2. **One assertion per test** - Each test should verify one specific behavior
3. **Use fixtures** - Share common setup through fixtures in conftest.py
4. **Test edge cases** - Include tests for empty inputs, invalid data, etc.
5. **Mock external dependencies** - Use `unittest.mock` for external API calls
6. **Keep tests fast** - Unit tests should run quickly

## Continuous Integration

These tests can be integrated into CI/CD pipelines:

```yaml
# Example GitHub Actions workflow
- name: Run tests
  run: pytest tests/ -v
```

## Troubleshooting

### Import errors
If you get import errors, make sure you're running pytest from the `course-architect` directory and that the package is installed in editable mode:
```bash
pip install -e .
```

### Module not found
If you see `ModuleNotFoundError: No module named 'src'`, ensure the working directory is `course-architect` and run:
```bash
pytest
```

### Async test issues
If you have async tests, they should be decorated with `@pytest.mark.asyncio`:
```python
@pytest.mark.asyncio
async def test_async_function():
    result = await async_function()
    assert result is not None
```
