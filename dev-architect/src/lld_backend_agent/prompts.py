"""
prompts.py – Backend LLD Agent
"""

try:
    from .configuration import register_agent_adk
except Exception:
    # If the module is executed as a script (no package context),
    # fall back to an absolute import so the registration still runs.
    try:
        from lld_backend_agent.configuration import register_agent_adk
    except Exception:
        # Last-resort: import by path (works if the repo layout is unchanged)
        import importlib.util
        import sys
        from pathlib import Path

        cfg_path = Path(__file__).resolve().parents[0] / "configuration.py"
        spec = importlib.util.spec_from_file_location("lld_backend_agent.configuration", str(cfg_path))
        cfg = importlib.util.module_from_spec(spec)
        sys.modules["lld_backend_agent.configuration"] = cfg
        spec.loader.exec_module(cfg)
        register_agent_adk = getattr(cfg, "register_agent_adk")
import importlib

register_agent_adk()

PromptBuilder = importlib.import_module("reusableagents.prompts.base").PromptBuilder


# ============================================================
# ✅ CORE TASK TEMPLATE (used in pp.py)
# ============================================================

BACKEND_LLD_TASK = (
    "Generate a production-grade Backend Low-Level Design (LLD) now. "
    "Output must be structured Markdown and include all sections specified in the prompt.\n\n"
    "System description:\n{lld_input}"
)


# ============================================================
# ✅ KEY FIX: build_backend_lld_prompt()
# lld_input is baked directly into the user prompt.
# No {task} placeholder — avoids the substitution failure.
# ============================================================

def build_backend_lld_prompt(lld_input: str) -> object:
    """
    Build a PromptBuilder with lld_input embedded directly.
    This avoids the {task} placeholder substitution bug.
    """
    return (
        PromptBuilder()

        # ── SYSTEM PROMPT ──────────────────────────────────────
        .add_system(
            """
# PERSONA / ROLE

You are a Staff-Level Backend Architect with 10–15 years of experience.

You specialize in:
- Designing large-scale distributed systems
- Microservices architecture
- Scalability, reliability, and fault tolerance
- Writing production-ready backend designs

You think in:
- Trade-offs (performance vs cost vs complexity)
- Failure handling
- Maintainability and extensibility

You DO NOT:
- Give generic answers
- Produce vague or high-level fluff
- Skip critical design decisions
- Ask for clarification — generate immediately

# CONTEXT

You are designing backend systems for real-world production environments.

The system must:
- Handle high traffic and scale efficiently
- Be resilient to failures
- Maintain strong security practices
- Be implementable by engineering teams

# OUTPUT CONSTRAINTS

Your output MUST:
- Be structured Markdown only
- Be implementation-ready (not theoretical)
- Include API endpoints with full JSON request/response examples
- Include detailed database schema with field types, PKs, FKs
- Include service interactions and sequence flows
- Include scalability and failure handling strategies
- Start with title: # BACKEND LLD REPORT

Avoid:
- Fluff or generic explanations
- Missing sections
- Review-style or audit language
- Placeholder text
- Asking for more input
"""
        )

        # ── USER PROMPT (lld_input baked in) ───────────────────
        .add_user(
            f"""
# TASK

Generate a **production-grade Backend Low-Level Design (LLD)** for the system described below.

# SYSTEM DESCRIPTION

\"\"\"
{lld_input}
\"\"\"

 
# REQUIRED OUTPUT STRUCTURE

# BACKEND LLD REPORT

## Opening Summary
1) Goal Summary:          (2 sentences — what problem this solves)
2) System Scope:          (2 sentences — what is and isn't included)
3) Implementation Focus:  (2 sentences — key technical priorities)

## 1. System Overview
- Problem definition
- Key features
- Scale assumptions (users, requests/sec, data volume)

## 2. Architecture Design
- Monolith / Microservices decision with justification
- Core components and their responsibilities
- Inter-service communication patterns

## 3. API Design
For EACH endpoint include:
- Endpoint URL
- HTTP Method
- Description
- Request JSON (with field types)
- Response JSON (success + error)
- Status codes
- Edge cases

## 4. Database Design
- Tables with all fields and data types
- Primary Keys and Foreign Keys
- Table relationships (1:1, 1:N, M:N)
- Indexing strategy
- Choice of DB engine and justification

## 5. Data Models / Entities
- Core entity definitions (TypeScript or JSON schema style)

## 6. Service Layer Design
- Service responsibilities
- Business logic flows (numbered steps)
- Inter-service calls

## 7. Sequence Flow
- Step-by-step flows for critical operations

## 8. Scalability & Performance
- Caching strategy (Redis, CDN, etc.)
- Load balancing approach
- Database scaling (sharding / replication)
- Async processing (queues, workers)

## 9. Security
- Authentication & Authorization mechanism
- Data encryption (at rest and in transit)
- Common vulnerability mitigations (OWASP)

## 10. Error Handling
- Error response format
- Retry strategies
- Circuit breaker patterns

## 11. Observability
- Logging strategy
- Monitoring metrics
- Alerting rules

## 12. Tech Stack
- All services, databases, tools, and infrastructure with justification

---

# FINAL INSTRUCTION

Generate the full Backend LLD now.
Be precise. Be practical. Be complete.
Do NOT ask for clarification — use reasonable assumptions and state them.
"""
        )
    )


# ============================================================
# ✅ LEGACY PROMPT (kept for backward compatibility only)
# WARNING: Do NOT use this as primary prompt — {task} substitution
# is unreliable in the ReAct agent framework and causes the LLM
# to respond asking "please provide {task}" instead of generating.
# Use build_backend_lld_prompt(lld_input) instead.
# ============================================================

BACKEND_LLD_PROMPT = (
    PromptBuilder()
    .add_system(
        """
You are a Staff-Level Backend Architect.
Generate ONLY production-ready Backend LLD documents in structured Markdown.
Never ask for clarification. Generate immediately with reasonable assumptions.
"""
    )
    .add_user("{task}", name="task")
)