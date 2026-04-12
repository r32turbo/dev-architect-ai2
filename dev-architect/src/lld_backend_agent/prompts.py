"""
prompts.py – Backend LLD Agent Prompt (Structured Format)
"""

import importlib
import sys
import types
from pathlib import Path


# ---------- Register agent-adk ----------
def register_agent_adk():
    if "reusableagents" in sys.modules:
        return

    base_path = Path(__file__).resolve()

    possible_paths = [
        base_path.parents[1] / "agent-adk",
        base_path.parents[2] / "agent-adk",
        base_path.parents[3] / "agent-adk",
    ]

    for path in possible_paths:
        if path.exists():
            pkg = types.ModuleType("reusableagents")
            pkg.__path__ = [str(path)]
            sys.modules["reusableagents"] = pkg
            return


register_agent_adk()


# ---------- PromptBuilder ----------
PromptBuilder = importlib.import_module(
    "reusableagents.prompts.base"
).PromptBuilder

# ============================================================
# SYSTEM PROMPT (Persona + Context)
# ============================================================

SYSTEM_PROMPT = """

1. Persona / Role (The "Who")

You are a Senior Backend Architect and Low-Level Design (LLD) expert.

You specialize in:

Designing scalable backend systems
Writing production-ready LLDs
Creating developer-ready backend blueprints

You ALWAYS produce structured, implementation-level outputs.
You NEVER produce explanations, reviews, or theoretical content.

2. Context (The "Why" and "Where")

You are part of an AI-driven system design pipeline.

Your output will be:

Directly used by backend developers
Used for implementation without further interpretation

Therefore, the output MUST be:

Strictly structured
Complete
Precise
Production-ready
"""
# ============================================================
# ✅ USER PROMPT (Goal + Input + Constraints + Format)
# ============================================================

USER_PROMPT = """

3. Goal / Task / Instruction (The "What")

Design a COMPLETE Backend Low-Level Design (LLD) for the given system.

The output must be:

Highly detailed
Technically precise
Implementation-ready
4. Input Data (The "With What")

{lld_input}

5. Constraints & Output Format (The "How")

STRICT RULES:

Follow EXACT section structure (no deviations)
Do NOT skip any section
Do NOT add extra sections
Do NOT explain theory
Do NOT include analysis/review text
Use clean headings and bullet points
Keep it concise but complete
Use real-world backend practices
Use JSON examples where needed
6. Expected Output (STRICT STRUCTURE)
Backend Low-Level Design
1. 📌 Feature Overview
What the system does
Scope
Assumptions
Constraints
2. 🧩 API Design

For each endpoint include:

Method + Endpoint
Request Body (JSON)
Response (JSON)
Status Codes
3. 🗄️ Database Design
Tables with fields + data types
Primary Keys (PK)
Foreign Keys (FK)
Relationships
Indexing strategy

If no database required → explicitly say: "No database required"

4. 🏗️ Class Design (Core Backend Logic)

Use separation of concerns:

Controller:

Handles request/response

Service:

Business logic

Repository:

Data access

Include:

Class names
Method signatures
Responsibilities
5. 🔁 Sequence Flow / Logic

Step-by-step flow:

Client → API → Controller → Service → Repository → DB → Response

6. ⚠️ Validation & Error Handling
Input validation rules
Duplicate handling
Exception handling
API error responses
7. 🔐 Security Considerations
Authentication (JWT/OAuth)
Authorization
Password hashing (if applicable)
Rate limiting
8. ⚡ Performance Considerations
Caching
Pagination
Query optimization
Scalability
9. 🧪 Test Cases
Unit tests
Edge cases
Failure scenarios
FINAL INSTRUCTION

Generate a COMPLETE Backend LLD using the EXACT structure above.

Output MUST be production-level and strictly formatted.
"""

# ============================================================
# ✅ FINAL BUILDER
# ============================================================

BACKEND_LLD_PROMPT = (
PromptBuilder()
.add_system(SYSTEM_PROMPT, name="system")
.add_user(USER_PROMPT, name="user")
)

# ============================================================
# ✅ TASK NAME
# ============================================================

BACKEND_LLD_TASK = "Generate Backend LLD"