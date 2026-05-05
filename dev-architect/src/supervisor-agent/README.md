# Supervisor Agent

## Overview

The Supervisor Agent is a central orchestration module that manages and supervises the execution of specialized agents (System Analyst, System Architect, Frontend LLD, Backend LLD, Generic LLD) within the architecture design system. It provides unified logging, dynamic module loading, and error handling across the entire multi-agent framework using the Agent Development Kit (ADK).

## Purpose

- **Multi-Agent Orchestration**: Coordinates execution of System Analyst, System Architect, and LLD agents
- **Unified Logging**: Dual-stream logging (file + stdout) for all agent activities and outputs
- **Dynamic Module Loading**: Intelligent loading of agent modules with path resolution
- **Output Chunking**: Efficiently handles large outputs through configurable chunking strategy
- **Worker Management**: Wraps agents as workers (e.g., `SystemAnalystWorker`) for supervised execution

## Key Features

### Logging & Output Management
- Dual-stream logging to both file and stdout (via `_Tee` class)
- Configurable output paths via `SUPERVISOR_OUTPUT_PATH` environment variable
- Automatic chunking of large outputs for memory efficiency
- Both human-readable and programmatic output formats
- State management for agent outputs via AgentContext

### Agent Coordination
- **Dynamic Module Resolution**: Automatically resolves entry points for each agent type
  - System Analyst: `analyst_agent.py` or `main.py`
  - System Architect: `sysaapp.py`
  - Frontend LLD: `frontend_graph.py`
  - Backend LLD: `lldbapp.py`
  - Generic LLD: Generic LLD agent
- **Worker Wrappers**: `SystemAnalystWorker` class wraps agents for supervised execution
- **ADK Integration**: Loads SupervisorAgent and supporting components from agent-adk
- **Context Passing**: Propagates AgentContext through worker chain

### Dependencies
- **Agents**: System Analyst, System Architect, Frontend LLD, Backend LLD, Generic LLD
- **Framework**: Agent Development Kit (ADK) with reusableagents
- **External**: LangChain, python-dotenv, importlib

## File Structure

```
supervisor-agent/
├── __init__.py              # Package initialization
├── sup.py                  # Main supervisor module and orchestration logic
└── README.md               # This file
```

## Core Functions & Classes

### Main Functions
- **`_load_module(module_name, file_path)`**: Dynamically loads a Python module from file path
- **`_resolve_*_entry_path()`**: Resolves entry points for each agent type:
  - `_resolve_system_analyst_entry_path()` → analyst_agent.py or main.py
  - `_resolve_system_architect_entry_path()` → sysaapp.py
  - `_resolve_frontend_lld_entry_path()` → frontend_graph.py
  - `_resolve_lld_backend_entry_path()` → lldbapp.py
  - `_resolve_generic_lld_entry_path()` → Generic LLD agent
- **`_chunk_text(text, chunk_size)`**: Splits text into configurable chunks
- **`_print_chunked_output(text)`**: Prints output in numbered chunks
- **`_write_full_output(text)`**: Writes complete output to file
- **`_store_agent_chunks(agent_key, output, context)`**: Stores chunked outputs in AgentContext

### Worker Classes
- **`SystemAnalystWorker`**: Wraps System Analyst Agent for supervised execution
  - `run(task, context)`: Executes system analysis with optional shared context
  - Automatically disables MLflow during supervision to avoid conflicts
  - Handles both agent.run() and run_system_analysis() calling conventions

### ADK Components
- **`_load_adk_components()`**: Loads from reusableagents package:
  - SupervisorAgent
  - WorkerSpec
  - AgentResponse
  - create_agent_llm
  - PromptBuilder
  - SupervisorConfig
  - ExecutionMode
  - GeminiConfig

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `SUPERVISOR_OUTPUT_PATH` | Path for supervisor output files | `{WORKSPACE_ROOT}/supervisor_output_latest.txt` |
| `SUPERVISOR_OUTPUT_CHUNK_SIZE` | Size of output chunks in characters | `6000` |

### Logging Configuration
The supervisor automatically configures logging on import:
- Log file location: Controlled by `SUPERVISOR_OUTPUT_PATH`
- Fallback log file: `{WORKSPACE_ROOT}/sup_output.txt`
- Format: `%(asctime)s | %(levelname)s | %(name)s | %(message)s`
- Handler types: Both file and console streams
- Stdout/stderr: Tee'd to log file via custom `_Tee` class

## Usage

### Using SystemAnalystWorker

```python
from supervisor_agent.sup import SystemAnalystWorker
from reusableagents.context import AgentContext  # Optional

# Create worker
worker = SystemAnalystWorker(agent_response_type=AgentResponse)

# Run analysis with optional context
result = worker.run(
    task="Analyze the system requirements",
    context=None  # Optional AgentContext instance
)
```

### Direct Module Loading

```python
from supervisor_agent.sup import _load_module
from pathlib import Path

# Load an agent module dynamically
module = _load_module(
    module_name="custom_agent",
    file_path=Path("/path/to/agent/main.py")
)

# Access functions from the module
result = module.some_function()
```

### Output Management

```python
from supervisor_agent.sup import _chunk_text, _print_chunked_output

# Process large output
text = "Very large output text..."
chunks = _chunk_text(text, chunk_size=6000)

# Print chunks with labels
_print_chunked_output(text)
```

## Integration Points

The Supervisor Agent coordinates with:

1. **System Analyst Agent** (`SystemAnalystWorker`)
   - Wraps analyst agent for supervised execution
   - Disables MLflow to prevent conflicts
   - Maintains context through supervised runs

2. **System Architect Agent** 
   - Entry point: `system_architect_agent/sysaapp.py`
   - Dynamically resolved and loaded

3. **Frontend LLD Agent**
   - Entry point: `frontend-lld-agent/frontend_graph.py`
   - LangGraph-based workflow

4. **Backend LLD Agent**
   - Entry point: `lld_backend_agent/lldbapp.py`
   - Supervised execution pattern

5. **Generic LLD Agent**
   - Multi-purpose LLD generation

## Error Handling

- **Module Not Found**: FileNotFoundError raised with expected paths
- **Logging Configuration Failure**: Continues without file logging
- **MLflow Conflicts**: Observability disabled during supervised runs
- **Context Issues**: Graceful fallback when AgentContext unavailable
- **Output Writing**: Warnings logged, execution continues

## Troubleshooting

### Logs Not Appearing
- Verify `SUPERVISOR_OUTPUT_PATH` is writable directory or valid file path
- Check stderr for IO permission errors
- Ensure parent directory exists and is accessible

### Module Resolution Failures
- Verify agent directories exist with correct entry point files
- Check agent names match configured resolver functions
- Ensure sys.path includes agent directory parents

### Output Not Chunked
- Verify `SUPERVISOR_OUTPUT_CHUNK_SIZE` is reasonable (minimum ~500)
- Check if output size exceeds chunk size
- Review `_chunk_text()` logic for edge cases

## Development Notes

- Uses importlib for dynamic module loading at runtime
- Thread-safe logging via dual-stream `_Tee` class
- Module introspection for flexible agent integration
- Supports both file objects and Path instances
- AgentContext integration for state propagation

## Related Components

- [System Analyst Agent](../system-analyst-agent/README.md)
- [System Architect Agent](../system_architect_agent/README.md)
- [Low-Level Design Agent](../low-level-design-agent/README.md)
- [Frontend LLD Agent](../frontend-lld-agent/README.md)
- [Backend LLD Agent](../lld_backend_agent/README.md)
