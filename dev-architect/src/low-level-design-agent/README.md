# Low-Level Design Agent

## Overview

The Low-Level Design (LLD) Agent is a specialized LLM-powered component that transforms high-level requirements and architecture specifications into detailed, implementation-ready low-level design documents. It uses a LangGraph StateGraph with a three-stage pipeline to progressively refine requirements into comprehensive technical specifications.

## Purpose

- **LLD Document Generation**: Create detailed, implementation-ready low-level design documents
- **Multi-Stage Refinement**: Break down design requirements through extract → analyze → generate pipeline
- **Requirements Synthesis**: Integrate user goals, requirements documents, and architecture documents
- **Implementation Planning**: Produce concrete implementation decisions with ordered steps
- **Technical Specifications**: Define component contracts, data flows, APIs, and error handling

## Key Features

### LangGraph State Machine Pipeline

The agent uses a three-node LangGraph workflow:

1. **Extract Sections** (`extract_sections` node)
   - Extracts concrete build requirements from input
   - Produces structured requirement sections
   - Balanced synthesis of all input sources

2. **Analyze Architecture** (`analyze_architecture` node)
   - Converts extracted requirements to implementation decisions
   - Creates technical implementation plan
   - Generates ordered assembly steps

3. **Generate Report** (`generate_report` node)
   - Creates final LLD document
   - Integrates all analysis stages
   - Produces implementation-ready output

### State Management
- Uses **LLDAgentState** TypedDict for type-safe state
- Tracks throughout pipeline:
  - `lld_input`: Input document
  - `requirement_doc`: Requirements reference
  - `architecture_doc`: Architecture reference
  - `sections`: Extracted sections from stage 1
  - `architecture_analysis`: Analysis from stage 2
  - `final_report`: Final LLD output

### LLM Integration
- **Model**: ChatGroq with `llama-3.3-70b-versatile`
- **Temperature**: 0.0 (deterministic output)
- **Framework**: LangGraph + LangChain
- **Execution**: Direct graph invocation via `.invoke()`

### Document Processing
- Safe handling of curly braces in prompts ({{ }} escaping)
- Markdown-formatted output
- Grounded decisions without speculation
- Explicit input attribution

## File Structure

```
low-level-design-agent/
├── __init__.py              # Package initialization
├── app.py                  # Main graph definition and node functions
├── state.py                # LLDAgentState definition and sample input
├── prompts.py              # Prompt templates for each stage
├── configuration.py        # Pydantic Configuration model
├── tools_and_schemas.py    # Tool definitions and schemas
├── graph.py                # (Derived from app.py nodes)
├── lld_createagent.py      # Agent creation utilities
├── utils.py                # Utility functions
├── __pycache__/            # Python cache
└── README.md               # This file
```

## Core Components

### Main Graph (app.py)
Defines the complete LLM-based LLD generation pipeline:

```python
builder = StateGraph(LLDAgentState)
builder.add_node("extract_sections", extract_sections)
builder.add_node("analyze_architecture", analyze_architecture)
builder.add_node("generate_report", generate_report)
builder.add_edge(START, "extract_sections")
builder.add_edge("extract_sections", "analyze_architecture")
builder.add_edge("analyze_architecture", "generate_report")
builder.add_edge("generate_report", END)
graph = builder.compile()
```

### Stage Nodes

#### `extract_sections(state: LLDAgentState) -> dict[str, str]`
- **Input**: `lld_input` document
- **Prompts**: SECTION_EXTRACTION_PROMPT
- **Output**: `sections` field with structured requirements
- **Sections Generated**:
  - Website Objective
  - Core Sections
  - Data and Content Requirements
  - Integration and Styling Requirements
  - Non-Functional Constraints

#### `analyze_architecture(state: LLDAgentState) -> dict[str, str]`
- **Input**: `sections` from stage 1
- **Prompts**: ARCHITECTURE_ANALYSIS_PROMPT
- **Output**: `architecture_analysis` field
- **Plan Sections**:
  - Component Assembly Plan
  - Data Contracts and State Flow
  - API and Integration Contracts
  - Rendering, Performance, and Accessibility Decisions
  - Error Handling and Operational Safeguards

#### `generate_report(state: LLDAgentState) -> dict[str, str]`
- **Input**: `architecture_analysis` from stage 2
- **Prompts**: REPORT_GENERATION_PROMPT
- **Output**: `final_report` field
- **Report Structure**: Implementation-ready LLD document

### State Definition (state.py)
```python
class LLDAgentState(TypedDict):
    lld_input: str
    requirement_doc: str
    architecture_doc: str
    sections: str
    architecture_analysis: str
    final_report: str
```

### Configuration (configuration.py)
Uses Pydantic BaseModel for configuration:
```python
class Configuration(BaseModel):
    query_generator_model: str = "gemini-2.0-flash"
    reflection_model: str = "gemini-2.5-flash"
    answer_model: str = "gemini-2.5-pro"
```

### Prompts (prompts.py)
Three prompt templates:

1. **SECTION_EXTRACTION_PROMPT**
   - Extracts concrete build requirements
   - Emphasizes balanced input treatment
   - Enforces no speculation

2. **ARCHITECTURE_ANALYSIS_PROMPT**
   - Converts requirements to decisions
   - Produces implementation plan
   - Shows decision rationale

3. **REPORT_GENERATION_PROMPT**
   - Generates final LLD document
   - Integrates all sources
   - Creates implementation-ready output

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `GROQ_API_KEY` | Groq API key for LLM access | Required |
| `LLD_MODEL` | LLM model name | `llama-3.3-70b-versatile` |
| `LLD_TEMPERATURE` | LLM temperature (0-1) | `0` |

### LLM Configuration
Default LLM setup in app.py:
```python
llm = ChatGroq(
    model="llama-3.3-70b-versatile",
    temperature=0,
)
```

## Usage

### Basic Graph Execution

```python
from low_level_design_agent.app import graph
from low_level_design_agent.state import LLDAgentState

# Prepare input state
input_state = {
    "lld_input": "Your design document...",
    "requirement_doc": "Requirements...",
    "architecture_doc": "Architecture...",
    "sections": "",
    "architecture_analysis": "",
    "final_report": ""
}

# Execute the graph
result = graph.invoke(input_state)

# Access final output
print(result["final_report"])
```

### Using LLD Sample Input

```python
from low_level_design_agent.app import graph
from low_level_design_agent.state import LLD_INPUT

# Use pre-defined example
result = graph.invoke({"lld_input": LLD_INPUT})
print(result["final_report"])
```

### Standalone Execution

```bash
# Direct execution from app.py __main__
python app.py

# Output:
# ------ LLD REVIEW REPORT ------
# [Final LLD report printed here]
```

## Output Structure

The generated LLD report includes:

### Stage 1: Section Extraction
- Website Objective
- Core Sections (components, features)
- Data and Content Requirements
- Integration and Styling Requirements
- Non-Functional Constraints

### Stage 2: Architecture Analysis
- Component Assembly Plan (ordered steps)
- Data Contracts and State Flow
- API and Integration Contracts
- Rendering, Performance, Accessibility Decisions
- Error Handling and Operational Safeguards

### Stage 3: Final Report
- Title: # LLD REPORT
- Opening block (3 labeled paragraphs)
- Complete implementation sections
- Code structure recommendations
- Testing strategy

## Key Design Principles

1. **Balanced Input Treatment**: All inputs (user goal, requirements, architecture) treated equally
2. **Implementation Focus**: Output is actionable and ready for development
3. **No Speculation**: Decisions grounded in provided inputs
4. **Clear Contracts**: Data and API contracts are explicit
5. **Markdown Format**: Easy integration with documentation

## Integration Points

- **Upstream**: Receives refined requirements from System Analyst Agent
- **Upstream**: Receives architecture from System Architect Agent
- **Downstream**: Outputs directly to development teams
- **Orchestration**: Supervised by Supervisor Agent

## Advanced Features

### Custom Node Implementation

```python
from langgraph.graph import StateGraph, START, END
from low_level_design_agent.state import LLDAgentState

# Create custom graph variant
custom_graph = StateGraph(LLDAgentState)
# Add custom nodes...
custom_graph.compile()
```

### State Inspection

```python
# Access intermediate state after each node
state_after_extract = result["sections"]
state_after_analyze = result["architecture_analysis"]
final_output = result["final_report"]
```

### Batch Processing

```python
from low_level_design_agent.app import graph

components = [
    {"lld_input": "Component 1...", "requirement_doc": "...", "architecture_doc": "..."},
    {"lld_input": "Component 2...", "requirement_doc": "...", "architecture_doc": "..."},
]

for component in components:
    result = graph.invoke(component)
    # Process result
```

## Performance Considerations

- **Temperature**: Set to 0.0 for deterministic results
- **Model**: Llama 3.3-70B optimized for speed and quality
- **Pipeline**: Three sequential LLM calls (can be parallelized if needed)
- **Token Usage**: Moderate per component (depends on document size)

## Troubleshooting

### Import Errors
- Verify all files present: app.py, state.py, prompts.py, configuration.py
- Check Python path includes agent directory
- Ensure agent-adk is accessible if using ADK components

### Graph Execution Errors
- Verify all LLDAgentState fields initialized
- Check input document format and content
- Ensure GROQ_API_KEY set and valid
- Verify Groq API rate limits

### Poor Quality Output
- Review and expand input documents
- Ensure architecture_doc is detailed
- Check user goal clarity
- Try adjusting model via LLD_MODEL environment variable

### API/Rate Limit Errors
- Verify GROQ_API_KEY is valid
- Check Groq API quota and rate limits
- Add retry logic for production use
- Consider async execution for batch processing

## Development Notes

- Uses LangGraph for workflow orchestration
- Type hints throughout (LLDAgentState TypedDict)
- Modular design allows easy extension
- Comprehensive error handling
- Prompt engineering for high-quality outputs
- Safe escaping of braces in prompt formatting

## Related Agents

- [Supervisor Agent](../supervisor-agent/README.md)
- [System Analyst Agent](../system-analyst-agent/README.md)
- [System Architect Agent](../system_architect_agent/README.md)
- [Frontend LLD Agent](../frontend-lld-agent/README.md)
- [Backend LLD Agent](../lld_backend_agent/README.md)
