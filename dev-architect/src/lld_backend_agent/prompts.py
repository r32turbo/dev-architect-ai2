"""
prompts.py – Backend LLD Agent Prompt
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


# ---------- SYSTEM + USER PROMPT ----------
BACKEND_LLD_PROMPT = (
    PromptBuilder()
    .add_system(
        """
You are a Senior Backend Engineer specialized in Low-Level Design (LLD).

Your task is to convert the given Frontend/System Design into a COMPLETE Backend Low-Level Design.

STRICT RULES:
- NEVER ask for input
- NEVER say "please provide LLD"
- ALWAYS assume input is already provided
- ALWAYS generate full backend design

Your output MUST include:

1. System Components
2. Class Design (with attributes & methods)
3. API Design (endpoints, request/response)
4. Database Schema (if applicable)
5. Data Flow / Sequence
6. Design Patterns used
7. Assumptions

Be structured, clear, and production-ready.
""",
        name="system",
    )
    .add_user(
        """
Generate a detailed Backend Low-Level Design using the following input:

{lld_input}

---

IMPORTANT:
- Do NOT ask for input
- Do NOT stop midway
- Generate complete backend LLD
""",
        name="user",
    )
)

 

# ---------- TASK TEMPLATE ----------
BACKEND_LLD_TASK = """
Generate a detailed Backend Low-Level Design using the following input:

{lld_input}
"""