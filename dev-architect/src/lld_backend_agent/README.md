# Backend LLD Agent (Strict Generator Mode)

##   Overview

The **Backend LLD Agent** is an AI-powered agent built using the **agent-adk framework** and **Google Gemini (Vertex AI)**. It generates a complete **Backend Low-Level Design (LLD)** document from a backend requirement or system description.

The agent operates in **STRICT GENERATOR MODE**, meaning it produces only clean final output without reasoning traces, analysis, or review sections.

It follows the **ReAct (Reasoning + Acting)** pattern internally and includes controlled validation to ensure high-quality results without overriding generation.

---

##   What It Does

A Backend LLD bridges the gap between system requirements and actual backend implementation.

While architecture defines **WHAT** the system does, this agent defines **HOW** the backend is built.

The agent generates a structured Backend LLD document including:

1. **API Design** — Endpoints, request/response models, validation rules
2. **Database Schema** — Tables, fields, indexes, relationships
3. **Service Layer Design** — Business logic and modular structure
4. **Caching Strategy** — Performance optimization using caching
5. **Sequence Flow** — Request lifecycle and execution steps
6. **Error Handling & Edge Cases** — Failures, validations, fallback logic

---

##  Project Structure

```
backend-lld-agent/
├── __init__.py         # Package marker
├── configuration.py    # Gemini + Agent configuration settings
├── graph.py            # Agent builder (ReAct agent setup)
├── prompts.py          # Prompt and task definitions
├── lldback.py          # Core backend LLD generation logic
├── lldbapp.py          # FastAPI app / API layer
├── state.py            # Agent state management
├── utils.py            # Helper utilities (chunking, cleaning, etc.)
└── agent-adk/          # Reusable agent framework (external dependency)
```

---

##   Input Schema

The agent is executed via:

```python
run_backend_lld()
```

| Field       | Type           | Required | Description                                      |
| ----------- | -------------- | -------- | ------------------------------------------------ |
| `lld_input` | `string`       | ✅ Yes    | Backend requirement or system description        |
| `context`   | `AgentContext` | ❌ No     | Optional context containing `state["lld_input"]` |

---

##  Input Resolution Logic

The agent resolves input in the following order:

1. Direct `lld_input` argument
2. `context.state["lld_input"]`
3. Raises `ValueError` if no input is found

---

##   Output Schema

| Type     | Description                            |
| -------- | -------------------------------------- |
| `string` | Final Backend LLD document in Markdown |

---

##   Output Behavior

* Returns **only clean LLD output** (Strict Generator Mode)
* Removes unwanted terms:

  * `"review"`
  * `"strength"`
  * `"weakness"`
  * `"analysis"`
* Handles large inputs using chunking and merges results

---

##   Chunking Strategy

For large inputs:

* **Chunk Size:** 8000 characters
* **Overlap:** 500 characters
* Splits at sentence boundaries
* Each chunk processed independently
* Outputs merged into final LLD

---

##   Database Schema

When used with FastAPI, results are stored in the `lld_documents` table:

| Column       | Type           | Description                |
| ------------ | -------------- | -------------------------- |
| `id`         | `INTEGER`      | Auto-increment primary key |
| `agent_type` | `VARCHAR(50)`  | `"backend_lld"`            |
| `lld_input`  | `TEXT`         | Backend requirement        |
| `output`     | `TEXT`         | Generated LLD document     |
| `session_id` | `VARCHAR(100)` | Optional session ID        |
| `created_at` | `DATETIME`     | Timestamp (UTC)            |

---

##   How to Call the Agent

### 1 Direct Python Call

```python
from lldback import run_backend_lld

lld_input = """
Design a backend for a URL shortener system.
Include APIs, DB schema, caching, and redirection logic.
"""

output = run_backend_lld(lld_input=lld_input)

print(output)
```

---

### 2 Via Postman

**Method:** `POST`
**URL:** `http://localhost:8000/generate/backend-lld`

**Headers:**

```
Content-Type: application/json
```

**Request Body:**

```json
{
  "lld_input": "Design a backend for a URL shortener system. Include APIs, DB schema, caching, and redirection logic."
}
```

**Response:**

```json
{
  "id": 1,
  "agent_type": "backend_lld",
  "lld_input": "Design a backend for a URL shortener system...",
  "output": "## Backend Low-Level Design (LLD)\n\n...",
  "created_at": "2026-05-03 10:30:00"
}
```

---

### 3 Via Swagger UI

1. Open browser: `http://localhost:8000/docs`
2. Select `POST /generate/backend-lld`
3. Click **Try it out**
4. Enter request JSON
5. Click **Execute**
6. View response

---

##   Configuration

Defined in `configuration.py`:

| Setting                      | Value                     | Description              |
| ---------------------------- | ------------------------- | ------------------------ |
| `project_id`                 | `"eds-alchemy"`           | GCP project ID           |
| `location`                   | `"us-central1"`           | Vertex AI region         |
| `agent_model`                | `"gemini-2.5-flash-lite"` | LLD generation model     |
| `validator_model`            | `"gemini-2.5-flash-lite"` | Validation model         |
| `agent_temperature`          | `0.0`                     | Deterministic output     |
| `validator_temperature`      | `0.0`                     | Stable validation        |
| `max_react_iterations`       | `3`                       | Limits reasoning loops   |
| `enable_validation`          | `True`                    | Enables validation       |
| `validation_score_threshold` | `0.5`                     | Avoids blocking output   |
| `max_refinement_attempts`    | `1`                       | Prevents over-refinement |

---

##   Dependencies

```
agent-adk
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
pip install agent-adk langchain-google-vertexai langgraph langchain sqlalchemy fastapi uvicorn
```

---

##   Authentication

Uses Google Cloud Application Default Credentials:

```bash
gcloud auth application-default login
```

---

##   Real Flow

```
User Input
     ↓
(Optional Context from Analyst / Architect)
     ↓
Backend LLD Agent
     ↓
Generated Backend LLD Document
```
 
 
##  License

This project is intended for educational and internal development use.
