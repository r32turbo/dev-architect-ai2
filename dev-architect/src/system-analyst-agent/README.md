# System Analyst Agent

## Overview

The System Analyst Agent is a specialized LLM-powered component that analyzes system requirements and goals to produce comprehensive design specifications. It uses a ReusableReActAgent pattern from the Agent Development Kit, with support for large document processing through intelligent chunking and MLflow observability.

## Purpose

- **System Analysis**: Deep LLM-based analysis of system requirements and goals
- **Requirement Comprehension**: Extract and synthesize key requirements from input
- **Design Specification Generation**: Produce structured design specifications from analysis
- **Context Integration**: Synthesize user goals, requirement documents, and architecture documents
- **Observability**: Full MLflow tracking and logging for experiment analysis

## Key Features

### Core Agent Pattern
- Uses **ReusableReActAgent** from Agent Development Kit (ADK)
- Google Gemini LLM integration (gemini-2.5-flash-lite by default)
- Direct agent execution via `agent.run(user_goal=...)`
- Integration with AgentContext for supervised execution

### Document Processing
- Intelligent text chunking with configurable overlap
- Preserves context boundaries at paragraph breaks
- Handles very large inputs by processing in chunks
- Deduplication of repeated content across chunks
- Normalization of output (removes conversational preamble, enforces markdown)

### LLM Integration
- **Primary Model**: ChatVertexAI (Google Gemini via VertexAI)
- **Model**: `gemini-2.5-flash-lite` (configurable)
- **Temperature**: 0.0 (deterministic)
- **Framework**: LangChain/LangGraph
- **ReAct Pattern**: Supports reasoning with tools (currently empty tools list)

### Multi-Input Synthesis
- **User Goal**: Primary instruction
- **Requirement Document**: Supporting context (equal importance)
- **Architecture Document**: Supporting context (equal importance)
- Explicit instructions to treat all three sources equally
- Guidance for agent to indicate which input influenced decisions

### Configuration Management
- Environment-based configuration
- Flexible parameter tuning
- Validation of configuration parameters
- Support for context-based input resolution

## File Structure

```
system-analyst-agent/
├── __init__.py              # Package initialization
├── analyst_agent.py         # Main agent and run_system_analysis() function
├── main.py                 # Standalone entry point with LLM setup
├── config.py               # Configuration and ADK component loading
├── prompt.py               # System analyst system prompt
├── prompts_builder.py      # Dynamic prompt construction utilities
├── react_agent.py          # ReusableReActAgent implementation
├── validator.py            # Input/output validation
├── observability.py        # MLflow and logging setup
├── lowlvl.py              # Low-level utility functions
├── mlflow.db              # MLflow tracking database
└── README.md              # This file
```

## Core Functions & Classes

### Main Entry Point
- **`run_system_analysis(user_goal=None, context=None) -> str`**
  - Primary function for executing system analysis
  - Accepts optional user goal and AgentContext
  - Returns normalized markdown output
  - Handles chunking, deduplication, and supporting document integration
  - MLflow tracking if observability enabled
  - State management via AgentContext

### Agent Building
- **`build_agent(context=None) -> ReusableReActAgent`**
  - Creates and configures the ReusableReActAgent
  - Loads system prompt with optional supporting docs
  - Builds prompt via PromptBuilder
  - Configures validator (no validation by default)
  - Returns ready-to-run agent

### Utility Functions
- **`load_environment()`**: Searches up directory tree for .env file
- **`load_adk_components()`**: Loads required classes from agent-adk:
  - ReusableReActAgent
  - PromptBuilder
  - AgentConfig
  - OutputValidator
  - GeminiConfig
  - create_agent_llm
  - create_validator_llm
- **`_initialize_observability()`**: Sets up MLflow one-time (non-blocking)
- **`_get_chunking_config()`**: Returns chunk size and overlap from env
- **`_chunk_text(text, chunk_size, chunk_overlap)`**: Intelligent text chunking
- **`_resolve_user_goal(user_goal, context)`**: Resolves goal from parameter or context
- **`normalize_analyst_output(text)`**: Cleans output (removes preamble, adds heading if needed)
- **`deduplicate_output(text)`**: Removes repeated markdown chunks
- **`normalize_text(text)`**: Lowercases and normalizes characters
- **`main()`**: CLI entry point

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `SYSTEM_ANALYST_CHUNK_SIZE_CHARS` | Size of text chunks for processing | `8000` |
| `SYSTEM_ANALYST_CHUNK_OVERLAP_CHARS` | Overlap between chunks for context | `800` |
| `SYSTEM_ANALYST_OBSERVABILITY_ENABLED` | Enable MLflow tracking | `0` (disabled) |
| `SYSTEM_ANALYST_REQUIREMENT_DOC` | Requirement document for standalone runs | `""` |
| `SYSTEM_ANALYST_ARCHITECTURE_DOC` | Architecture document for standalone runs | `""` |
| `GOOGLE_CLOUD_PROJECT` | GCP project ID | `eds-alchemy` |
| `GOOGLE_CLOUD_LOCATION` | GCP region | `us-central1` |
| `GEMINI_AGENT_MODEL` | Gemini model for agent | `gemini-2.5-flash-lite` |
| `GEMINI_VALIDATOR_MODEL` | Gemini model for validation | `gemini-2.5-flash-lite` |

### Chunking Configuration

- **Minimum chunk size**: 1000 characters
- **Overlap validation**: Capped at 10% of chunk size if too large
- **Paragraph preservation**: Breaks at paragraph boundaries (\n\n) when possible
- **Line preservation**: Falls back to line breaks (\n) if needed

## Usage

### Basic Usage - Direct Function Call

```python
from system_analyst_agent.analyst_agent import run_system_analysis

# Simple analysis
result = run_system_analysis(
    user_goal="Design a user authentication system for a web application"
)
print(result)
```

### Usage with Supporting Documents

```python
from system_analyst_agent.analyst_agent import run_system_analysis
from reusableagents.context import AgentContext

# Create context with supporting docs
context = AgentContext()
context.state = {
    "user_goal": "Design a user authentication system",
    "requirement_doc": "Requirements: OAuth2, JWT tokens, MFA support...",
    "architecture_doc": "Microservices architecture with API Gateway..."
}

# Run analysis
result = run_system_analysis(context=context)
```

### Standalone Entry Point

```bash
# Using main.py directly
python main.py --user-goal "Design a real-time notification system"

# With environment variables
export SYSTEM_ANALYST_REQUIREMENT_DOC="path/to/requirements.md"
export SYSTEM_ANALYST_ARCHITECTURE_DOC="path/to/architecture.md"
python main.py --user-goal "System goal here"
```

### Agent Building and Direct Execution

```python
from system_analyst_agent.analyst_agent import build_agent

# Build the agent
agent = build_agent(context=None)

# Run directly with ReAct pattern
result = agent.run(user_goal="Analyze system requirements")
output = result.output if hasattr(result, "output") else str(result)
```

## Integration Points

- **Upstream**: Receives input from Supervisor Agent via SystemAnalystWorker
- **Downstream**: Output feeds to System Architect or Low-Level Design agents
- **Monitoring**: MLflow for experiment tracking (optional)
- **Logging**: Centralized logging via supervisor

## Advanced Features

### Custom Prompt Building

```python
from system_analyst_agent.prompts_builder import PromptBuilder

builder = PromptBuilder()
custom_prompt = builder.add_system("Custom system prompt")
custom_prompt = builder.add_user("{user_goal}")
```

### Enabling Observability

```bash
export SYSTEM_ANALYST_OBSERVABILITY_ENABLED=1
# Run analysis - metrics will be tracked in MLflow
python -m system_analyst_agent.analyst_agent
```

### Processing Large Documents

```python
from system_analyst_agent.analyst_agent import run_system_analysis

# Automatic chunking for large inputs
result = run_system_analysis(
    user_goal="Very long system specification..."  # Will auto-chunk
)
```

## Performance Notes

- **Chunking overhead**: Minimal for documents under 8000 chars
- **Token efficiency**: Chunk overlap preserves context between chunks
- **Output deduplication**: Removes repeated analysis across chunks
- **MLflow impact**: Non-blocking; errors don't halt execution
- **LLM calls**: One per chunk + optional validation calls

## Troubleshooting

### Chunking Issues
- Minimum chunk size enforced at 1000 characters
- Overlap auto-adjusted if >= chunk size
- Increase `SYSTEM_ANALYST_CHUNK_SIZE_CHARS` for fewer, larger chunks
- Check output deduplication if seeing repeated content

### Missing Output Sections
- Verify input documents are complete
- Check that user goal is clearly stated
- Ensure requirement/architecture docs are meaningful
- Review prompt formatting (double braces {{ }} for escaping)

### Observability Errors
- Verify MLflow database accessible at localhost:5000
- Set `SYSTEM_ANALYST_OBSERVABILITY_ENABLED=0` if MLflow unavailable
- Check MLflow logs for connection issues
- Observability errors never halt agent execution

### API/Model Errors
- Verify `GOOGLE_CLOUD_PROJECT` set correctly
- Check GCP authentication (Application Default Credentials)
- Verify model names are available in specified region
- Check rate limits and quota

## Development Notes

- Uses ReusableReActAgent pattern from ADK
- Type hints throughout for IDE support
- Modular design allows easy extension
- Comprehensive error handling (non-blocking)
- AgentContext support for framework integration
- Full MLflow instrumentation (optional)

## Related Agents

- [Supervisor Agent](../supervisor-agent/README.md)
- [System Architect Agent](../system_architect_agent/README.md)
- [Low-Level Design Agent](../low-level-design-agent/README.md)
