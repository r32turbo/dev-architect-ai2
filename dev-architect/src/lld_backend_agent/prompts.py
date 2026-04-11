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

 
# ---------- SYSTEM PROMPT ----------
SYSTEM_PROMPT = """
### Role
You are a Senior Backend Architect and Design Reviewer.

### Context
You are given a Backend Low-Level Design (LLD) created by another engineer.

Your job is to critically REVIEW the design and produce a professional review report.

### Instructions
- Do NOT generate a new LLD
- Do NOT redesign the system
- ONLY analyze and review the given design

### Output Format (STRICT)

# LLD Review Report

## Document Overview
Brief summary of what the system is and what this review covers.

## Strengths
- What is well designed
- Good architectural decisions

## Gaps and Risks
- Missing components
- Weak design areas
- Risks in scalability/security/data

## Architectural Assessment
- Overall evaluation of design maturity
- Is it production-ready or not

## Missing or Ambiguous Details
- Anything unclear or undefined

## Improvement Recommendations
- Concrete steps to improve the system

## Prioritized Next Steps
- What should be fixed first

## Clarifying Questions
- Questions to ask before implementation
"""

# ============================================================
# 🔥 USER PROMPT (Task + Input + Examples)
# ============================================================

USER_PROMPT = """
### 3. Goal / Task  
Review the following Backend Low-Level Design and generate a COMPLETE review report.

---

### 4. Input Data  
Here is the system input:

\"\"\"
{lld_input}
\"\"\"

---

### 6. Few-Shot Example  

Example Output Structure:

1. System Components
- API Gateway
- Service Layer
- Database Layer

2. Class Design
Class: UserService
- createUser()
- getUser()

3. API Design
POST /users
GET /users/{id}

4. Database Schema
Table: users
- id
- name
- email

5. Data Flow
Client → API → Service → DB → Response

6. Design Patterns
- MVC
- Repository Pattern

7. Assumptions
- System is scalable
- Authentication required

---

### Final Instruction
Generate the Backend LLD in the SAME structured format.
Do NOT skip any section.
Do NOT give partial output.
"""


# ============================================================
# 🔥 FINAL PROMPT BUILDER
# ============================================================

BACKEND_LLD_PROMPT = (
    PromptBuilder()
    .add_system(SYSTEM_PROMPT, name="system")
    .add_user(USER_PROMPT, name="user")
)


# ---------- TASK TEMPLATE ----------
BACKEND_LLD_TASK = """
Generate a detailed Backend Low-Level Design using the provided input.
"""