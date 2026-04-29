# Generic LLD Agent

## Overview

The **Generic LLD Agent** is an AI-powered agent built using **LangGraph** and **Google Gemini** (Vertex AI). It generates a complete **Generic Low-Level Design (LLD)** document from three inputs: a user request, a requirements document, and an architecture document.

The agent follows the **ReAct (Reasoning + Acting)** pattern using the `agent-adk` package. It includes built-in output validation and automatic refinement to ensure high-quality results.

---

## What It Does

A Generic LLD bridges the gap between a high-level architecture and actual code implementation. While the architecture document describes WHAT is being built, this LLD describes HOW it is built at the code level.

The agent generates a structured Generic LLD document with exactly 6 sections:

1. **Module & Component Specifications** — Detailed system hierarchy, interface/entity definitions with exact input/output types and state scope
2. **Data Models & Schema** — TypeScript interfaces or JSON schemas, storage strategy, mapping and transformation rules between modules
3. **Detailed Logic & Algorithms** — Step-by-step pseudocode for key features, behavioral rules and constraints, performance optimisation strategies
4. **Integration & Interface Design** — External API configuration, internal module communication contracts, environment variables and key management
5. **System Constraints & Styling (Technical Tokens)** — Framework/library rules, design tokens table (name/value/usage), breakpoints table
6. **Robustness: Error Handling & Edge Cases** — Error handling strategies, loading and success states, input validation and asset fallback rules

---

## Project Structure

```
generic-lld-agent/
├── __init__.py                  # Package marker
├── generic_configuration.py    # Registers agent-adk, GeminiConfig, AgentConfig, LLM factories
├── generic_graph.py             # ReusableReActAgent builder + AgentContext creator
└── generic_prompts.py           # PromptBuilder (WHO/WHAT/WHY/HOW/RULES/WITH structure)
```

---

## Input Schema

The agent accepts these inputs via `agent.run()`:

| Field | Type | Required | Description |
|---|---|---|---|
| `context` | `AgentContext` | ✅ Yes | Session context created by `create_context()` |
| `user_input` | `string` | ✅ Yes | The original user request (e.g. "Create an attendance management system") |
| `requirement_doc` | `string` | ✅ Yes | Requirements document from the System Analyst Agent |
| `architecture_doc` | `string` | ✅ Yes | Architecture document from the Architecture Agent |

---

## Output Schema

The agent returns an `AgentResponse` object:

| Field | Type | Description |
|---|---|---|
| `output` | `string` | The full generated Generic LLD document in Markdown |
| `is_validated` | `bool` | Whether the output passed validation |
| `validation_score` | `float` | Quality score from 0.0 to 1.0 |
| `validation_feedback` | `string` | Feedback from the validator LLM |
| `was_refined` | `bool` | Whether the output was refined after initial generation |
| `refinement_attempts` | `int` | Number of refinement attempts made |

---

## Database Schema

When called via FastAPI, the output is saved to the `lld_documents` table in `dev_architect.db`:

| Column | Type | Description |
|---|---|---|
| `id` | `INTEGER` | Auto-increment primary key |
| `agent_type` | `VARCHAR(50)` | Always `"generic_lld"` for this agent |
| `user_input` | `TEXT` | The original user request |
| `requirement_doc` | `TEXT` | The requirements document input |
| `architecture_doc` | `TEXT` | The architecture document input |
| `output` | `TEXT` | The generated LLD document in Markdown |
| `session_id` | `VARCHAR(100)` | The AgentContext session ID |
| `created_at` | `DATETIME` | Timestamp of document creation (UTC) |

---

## How to Call the Agent

### 1. Via Postman

**Method:** `POST`
**URL:** `http://localhost:8000/generate/generic-lld`

**Headers:**
```
Content-Type: application/json
```

**Request Body:**
```json
{
  "user_input": "Create a one-page marketing website for a business",
  "requirement_doc": "# Requirements\n- Display services (min 3, max 6)\n- Contact form\n- Responsive design\n- SEO optimized",
  "architecture_doc": "# Architecture\n- Next.js SPA\n- Tailwind CSS 4.0\n- Static Site Generation\n- Vercel deployment"
}
```

**Response:**
```json
{
  "id": 2,
  "agent_type": "generic_lld",
  "user_input": "Create a one-page marketing website for a business",
  "output": "## Generic Low-Level Design (LLD)\n\n...",
  "session_id": "550e8400-e29b-41d4-a716-446655440001",
  "created_at": "2026-04-26 10:35:00"
}
```

---

### 2. Via Swagger UI

1. Open browser: `http://localhost:8000/docs`
2. Click `POST /generate/generic-lld`
3. Click **Try it out**
4. Paste the request body JSON
5. Click **Execute**
6. View the response below

---

### 3. Via Python (Direct Function Call)

```python
import sys
sys.path.insert(0, "path/to/src/generic-lld-agent")

from generic_graph import build_agent, create_context

# Build the agent once
agent = build_agent()

# Create a context for this run
ctx = create_context(
    user_id="my-user",
    session_metadata={"source": "my-script"},
)

# Run the agent
response = agent.run(
    context=ctx,
    user_input="Create a one-page marketing website",
    requirement_doc="...",
    architecture_doc="...",
)

# Use the output
print(response.output)
print(f"Validation score : {response.validation_score}")
print(f"Was refined      : {response.was_refined}")
print(f"Refinement runs  : {response.refinement_attempts}")
```

---

## Configuration

Settings are defined in `generic_configuration.py`:

| Setting | Value | Description |
|---|---|---|
| `project_id` | `"eds-alchemy"` | GCP project ID |
| `location` | `"us-central1"` | Vertex AI region |
| `agent_model` | `"gemini-2.5-flash-lite"` | Gemini model for LLD generation |
| `validator_model` | `"gemini-2.5-flash-lite"` | Gemini model for validation |
| `agent_temperature` | `0.0` | Sampling temperature for agent LLM |
| `validator_temperature` | `0.0` | Sampling temperature for validator LLM |
| `max_react_iterations` | `5` | Max ReAct loop iterations |
| `enable_validation` | `True` | Enable output validation |
| `validation_score_threshold` | `0.7` | Minimum acceptable quality score (0.0–1.0) |
| `max_refinement_attempts` | `2` | Max refinement retries if validation fails |

---

## Dependencies

```
langchain-google-vertexai
langgraph
langchain
langchain-core
sqlalchemy
fastapi
uvicorn
```

Install:
```bash
pip install langchain-google-vertexai langgraph langchain sqlalchemy fastapi uvicorn
```

---

## Authentication

The agent uses Google Cloud Application Default Credentials:

```bash
gcloud auth application-default login
```

---

## Real Flow (Supervisor Pipeline)

In production this agent is called by the Supervisor Agent as part of a larger pipeline:

```
User sends request via FastAPI
          ↓
    Supervisor Agent
          ↓
System Analyst Agent  ──→  requirement_doc
          ↓
Architecture Agent    ──→  architecture_doc
          ↓
Generic LLD Agent  ←── (user_input + requirement_doc + architecture_doc)
          ↓
Output saved to database (lld_documents table)
          ↓
Response returned to user via FastAPI
```