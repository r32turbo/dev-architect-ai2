# System Architecture Agent

## Overview

The **System Architecture Agent** is an AI-powered agent built using a **ReAct (Reasoning + Acting)** architecture and **Google Gemini (Vertex AI)**. It generates a complete **High-Level Design (HLD)** document from a given system or analyst input document.

The agent enforces **STRICT HLD MODE**, meaning:

* The output must follow a fixed structure
* No sections can be skipped or added
* No vague or placeholder text is allowed

It ensures consistent, production-ready architecture documentation.

---

## What It Does

Given a system description or analyst document, the agent generates a structured **System Architecture Report** with exactly 10 sections:

1. **System Overview** — Purpose, scope, and target users
2. **Functional Requirements** — Core system features as bullet points
3. **Non-Functional Requirements** — Performance, scalability, reliability, security
4. **High-Level Architecture** — Client, backend, database, external APIs + architecture type (Monolithic/Microservices)
5. **System Components**

   * Frontend (tech + responsibilities)
   * Backend (business logic, APIs, auth)
   * Database (type + stored data)
   * APIs (REST/GraphQL usage)
6. **Data Flow** — Step-by-step request lifecycle
7. **Technology Stack** — Frontend, backend, database, cloud
8. **Scalability Considerations** — Load balancing, scaling, caching (Redis)
9. **Security Considerations** — JWT/OAuth, encryption, API protection
10. **Deployment Architecture** — Cloud, Docker, CI/CD

---

## Project Structure

```
system-architecture-agent/
├── __init__.py              # Package marker
├── configuration.py        # Gemini + Agent configuration
├── graph.py                # ReAct agent builder
├── prompts.py              # Prompt definitions (STRICT HLD prompt)
├── state.py                # Input/output state management
├── utils.py                # Helper utilities (chunking, cleaning)
├── tools_and_schemes.py    # Tool definitions (if used)
├── system_architect.py     # Main System Architecture Agent
├── sysaapp.py              # FastAPI app (API layer)
│
└── agent-adk/              # Reusable agent framework (external)
```

---

## Input Schema

The agent accepts the following input:

| Field            | Type     | Required | Description                                   |
| ---------------- | -------- | -------- | --------------------------------------------- |
| `input_document` | `string` | ✅ Yes    | System Analyst document or system description |

If not provided, the agent automatically fetches input from `ArchitectState`.

---

## Output Schema

The agent returns a **string output** (strict HLD document):

| Field    | Type     | Description                                 |
| -------- | -------- | ------------------------------------------- |
| `output` | `string` | Full System Architecture Report in Markdown |

Unlike LLD agents, this agent:

* ❌ Does NOT include validation metadata
* ❌ Does NOT return scores
* ✅ Focuses on strict structured output only

---

## Database Schema

When integrated with FastAPI, outputs are stored in `documents` table:

| Column           | Type          | Description              |
| ---------------- | ------------- | ------------------------ |
| `id`             | `INTEGER`     | Primary key              |
| `agent_type`     | `VARCHAR(50)` | `"system_architecture"`  |
| `input_document` | `TEXT`        | Input system description |
| `output`         | `TEXT`        | Generated HLD document   |
| `created_at`     | `DATETIME`    | Timestamp                |

---

## How to Call the Agent

### 1. Via Postman

**Method:** `POST`
**URL:** `http://localhost:8000/generate/system-architecture`

**Headers:**

```
Content-Type: application/json
```

**Request Body:**

```json
{
  "input_document": "Design a scalable system architecture for a URL shortener like Bitly. Include API design, database schema, caching, and load balancing."
}
```

**Response:**

```json
{
  "id": 10,
  "agent_type": "system_architecture",
  "output": "# System Architecture Report\n\n## 1. System Overview\n...",
  "created_at": "2026-05-03 16:00:00"
}
```

---

### 2. Via Swagger UI

1. Open: `http://localhost:8000/docs`
2. Select `POST /generate/system-architecture`
3. Click **Try it out**
4. Enter request body
5. Click **Execute**

---

### 3. Via Python (Direct Function Call)

```python
from system_architect import run_system_architect

input_doc = """
Design a scalable e-commerce platform with payment integration and high availability.
"""

output = run_system_architect(input_document=input_doc)

print(output)
```

---

## How It Works

### 1. Prompt Enforcement

* Uses a **strict system prompt**
* Ensures:

  * Fixed headings
  * No missing sections
  * Professional formatting

### 2. ReAct Agent Execution

* Built using `ReusableReActAgent`
* Runs with:

  * Max 5 iterations
  * Deterministic output (temperature = 0)

### 3. Chunking Support

* Large inputs are split using:

```python
chunk_text(text, chunk_size=8000, overlap=500)
```

* Each chunk is processed separately and merged

### 4. State Management

* Input fetched from `ArchitectState` if not provided
* Output stored back into state

---

## Configuration

| Setting                   | Value                   | Description               |
| ------------------------- | ----------------------- | ------------------------- |
| `agent_model`             | `gemini-2.5-flash-lite` | LLM for generation        |
| `validator_model`         | `gemini-2.5-flash-lite` | (Loaded but not enforced) |
| `temperature`             | `0.0`                   | Deterministic output      |
| `max_react_iterations`    | `5`                     | Reasoning steps           |
| `enable_validation`       | `False`                 | Disabled                  |
| `max_refinement_attempts` | `2`                     | Retry limit               |
| `chunk_size`              | `8000`                  | Max input size            |
| `overlap`                 | `500`                   | Context preservation      |

---

## Dependencies

```
langchain-google-vertexai
langgraph
langchain
fastapi
uvicorn
python-dotenv
```

Install:

```bash
pip install langchain-google-vertexai langgraph langchain fastapi uvicorn python-dotenv
```

---

## Authentication

Uses Google Cloud credentials:

```bash
gcloud auth application-default login
```

---

## Real Flow (Supervisor Pipeline)

```
User Request
     ↓
Supervisor Agent
     ↓
System Analyst Agent  → requirement_doc
     ↓
System Architecture Agent  ← (input_document)
     ↓
(Optional) Backend / Frontend LLD Agents
     ↓
Stored in Database
     ↓
Returned via FastAPI
```

---

## Key Notes

* STRICT format enforcement → No flexibility in sections
* Best suited for:

  * System design interviews
  * Architecture documentation
  * Pre-LLD planning
* Works as a **foundation agent** before LLD generation

---
## License

This project is intended for educational and internal development use.

## Author

Built as part of an **AI-driven multi-agent system design pipeline** using ReAct architecture and Gemini LLM.

