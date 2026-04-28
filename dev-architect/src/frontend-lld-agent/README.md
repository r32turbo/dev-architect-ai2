# Frontend LLD Agent

## Overview

The **Frontend LLD Agent** is an AI-powered agent built using **LangGraph** and **Google Gemini** (Vertex AI). It generates a complete **Frontend Low-Level Design (LLD)** document from three inputs: a user request, a requirements document, and an architecture document.

The agent follows the **ReAct (Reasoning + Acting)** pattern using the `agent-adk` package. It includes built-in output validation and automatic refinement to ensure high-quality results.

---

## What It Does

Given a user request and supporting documents, the agent generates a structured Frontend LLD document with exactly 6 sections:

1. **Module & Component Specifications** — Component hierarchy (nested bullet tree), TypeScript interfaces (NavItem, ServiceCardProps, ContactProps), state management (isMenuOpen, useActiveSection hook)
2. **Data Models & Schema** — SITE_DATA content schema in TypeScript, static asset pathing (/public/images/), lucide-react icon library
3. **Detailed Logic & Algorithms** — Smooth scrolling, Navbar offset handling, Next.js Image optimisation (LCP, CLS), SSG pre-rendering
4. **API & Integration Design** — Google Maps Embed API (iframe + geo: URI), optional contact form (POST /api/contact)
5. **Visual & Styling System** — Tailwind CSS 4.0 breakpoints table (sm/md/lg), design tokens (typography, colors)
6. **Error Handling & Edge Cases** — 404 page (not-found.tsx), map skeleton loader, image fallback (onError), SEO metadata (openGraph)

---

## Project Structure

```
frontend-lld-agent/
├── __init__.py                   # Package marker
├── frontend_configuration.py    # Registers agent-adk, GeminiConfig, AgentConfig, LLM factories
├── frontend_graph.py             # ReusableReActAgent builder + AgentContext creator
└── frontend_prompts.py           # PromptBuilder (WHO/WHAT/WHY/HOW/RULES/WITH structure)
```

---

## Input Schema

The agent accepts these inputs via `agent.run()`:

| Field | Type | Required | Description |
|---|---|---|---|
| `context` | `AgentContext` | ✅ Yes | Session context created by `create_context()` |
| `user_input` | `string` | ✅ Yes | The original user request (e.g. "Create a marketing website") |
| `requirement_doc` | `string` | ✅ Yes | Requirements document from the System Analyst Agent |
| `architecture_doc` | `string` | ✅ Yes | Architecture document from the Architecture Agent |

---

## Output Schema

The agent returns an `AgentResponse` object:

| Field | Type | Description |
|---|---|---|
| `output` | `string` | The full generated Frontend LLD document in Markdown |
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
| `agent_type` | `VARCHAR(50)` | Always `"frontend_lld"` for this agent |
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
**URL:** `http://localhost:8000/generate/frontend-lld`

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
  "id": 1,
  "agent_type": "frontend_lld",
  "user_input": "Create a one-page marketing website for a business",
  "output": "## Low-Level Design (LLD): One-Page Marketing Website\n\n...",
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "created_at": "2026-04-26 10:30:00"
}
```

---

### 2. Via Swagger UI

1. Open browser: `http://localhost:8000/docs`
2. Click `POST /generate/frontend-lld`
3. Click **Try it out**
4. Paste the request body JSON
5. Click **Execute**
6. View the response below

---

### 3. Via Python (Direct Function Call)

```python
import sys
sys.path.insert(0, "path/to/src/frontend-lld-agent")

from frontend_graph import build_agent, create_context

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

Settings are defined in `frontend_configuration.py`:

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
Frontend LLD Agent  ←── (user_input + requirement_doc + architecture_doc)
          ↓
Output saved to database (lld_documents table)
          ↓
Response returned to user via FastAPI
```