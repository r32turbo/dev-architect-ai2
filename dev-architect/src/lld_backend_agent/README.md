# Backend LLD Agent (Strict Generator Mode)

## Overview

The **Backend LLD Agent** is an AI-powered agent built using the **agent-adk framework** and **Google Gemini** (Vertex AI). It generates a complete **Backend Low-Level Design (LLD)** document from a backend requirement or system description.

The agent operates in **STRICT GENERATOR MODE**, meaning it produces only clean final output without reasoning traces, analysis, or review sections.

It follows the **ReAct (Reasoning + Acting)** pattern internally and includes output validation with controlled refinement to ensure high-quality results.

---

## What It Does

A Backend LLD bridges the gap between system requirements and actual backend implementation. 

The agent generates a structured Backend LLD document with the following sections:

1. **API Design** — Endpoints, request/response models, validation rules  
2. **Database Schema** — Tables, fields, indexes, relationships  
3. **Service Layer Design** — Business logic and modular structure  
4. **Caching Strategy** — Performance optimization using caching  
5. **Sequence Flow** — Request lifecycle and execution steps  
6. **Error Handling & Edge Cases** — Failures, validations, fallback logic  

---

## Project Structure
backend-lld-agent/
├── init.py # Package marker
├── configuration.py # Gemini + Agent configuration settings
├── graph.py # Agent builder (ReAct agent setup)
├── prompts.py # Prompt and task definitions
├── lldback.py # Core backend LLD generation logic
├── lldbapp.py # Application entry / API layer (if used)
├── state.py # Agent state management
├── utils.py # Helper utilities (chunking, cleaning, etc.)
└── agent-adk/ # Reusable agent framework (external dependency)


---

## Input Schema

The agent accepts input via the `run_backend_lld()` function:

| Field | Type | Required | Description |
|---|---|---|---|
| `lld_input` | `string` | ✅ Yes | Backend requirement or system description |
| `context` | `AgentContext` | ❌ No | Optional context containing `state["lld_input"]` |

---

## Input Resolution Logic

The agent resolves input in the following priority order:

1. Direct `lld_input` argument  
2. `context.state["lld_input"]`  
3. Raises `ValueError` if no input is found  

---

## Output Schema

The function returns:

| Type | Description |
|---|---|
| `string` | Final Backend LLD document in Markdown |

---

## Output Behavior

- Returns **only clean LLD output** (Strict Generator Mode)
- Removes unwanted terms:
  - "review"
  - "strength"
  - "weakness"
  - "analysis"
- Handles large inputs using chunking and merges results

---

## Chunking Strategy

To handle large inputs:

- **Chunk Size:** 8000 characters  
- **Overlap:** 500 characters  
- Splits at sentence boundaries  
- Each chunk is processed independently and merged  

---
## Database Schema

When called via FastAPI, the output is saved to the `lld_documents` table in `dev_architect.db`:

| Column | Type | Description |
|---|---|---|
| `id` | `INTEGER` | Auto-increment primary key |
| `agent_type` | `VARCHAR(50)` | Always `"backend_lld"` for this agent |
| `lld_input` | `TEXT` | Backend requirement or system description |
| `output` | `TEXT` | The generated Backend LLD document in Markdown |
| `session_id` | `VARCHAR(100)` | Optional AgentContext session ID |
| `created_at` | `DATETIME` | Timestamp of document creation (UTC) |

---

## How to Call the Agent

### 1. Direct Python Call

```python
from lldback import run_backend_lld

lld_input = """
Design a backend for a URL shortener system.
Include APIs, DB schema, caching, and redirection logic.
"""

output = run_backend_lld(lld_input=lld_input)
 
print(output)

 

### 2 Via Postman

**Method:** `POST`  
**URL:** `http://localhost:8000/generate/backend-lld`

**Headers:**

**Request Body:**
```json

{
  "id": 5,
  "agent_type": "backend_lld",
  "user_input": "Design a backend for a URL shortener system...",
  "output": "## Backend Low-Level Design (LLD)\n\n...",
  "created_at": "2026-05-03 10:30:00"
}
```

### 3 Via Swagger UI
Open browser: http://localhost:8000/docs
Click POST /generate/backend-lld
Click Try it out
Enter the lld_input JSON
Click Execute
View the generated LLD output

##  Dependencies
agent-adk
langchain-google-vertexai 
langgraph
langchain
langchain-core
sqlalchemy
fastapi
uvicorn

Install:

pip install agent-adk langchain-google-vertexai langgraph langchain sqlalchemy fastapi uvicorn

## Authentication

The agent uses Google Cloud Application Default Credentials:

```bash
gcloud auth application-default login
```
## Real Flow
In production, this agent can be part of a larger pipeline:

User Input
     ↓
System Analyst / Architect Outputs (optional)
     ↓
Backend LLD Agent
     ↓
Final Backend LLD Document