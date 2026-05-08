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
    Enhanced to generate comprehensive backend LLD with technical depth.
    
    CRITICAL: This prompt produces output in 6k-8k character range.
    Uses structured tables, compact bullets, and zero-redundancy rules.
    """
    escaped_input = lld_input.replace("{", "{{").replace("}", "}}")

    return (
        PromptBuilder()

        .add_system(
            "You are a Staff-level backend architect. Generate PRODUCTION-READY Backend LLD in Markdown. "
            "Output must be implementation-focused, technically deep, and concise. "
            "Use tables, structured bullets, and code blocks. Keep TOTAL output 10000-14000 meaningful characters. "
            "Focus on internal service implementation: folder layout, repository/service/controller layers, DTOs/entities, transactions, sagas, retries, idempotency, caching, and queue consumers/producers."
        )

        .add_system(
            "MANDATORY GENERATION RULES:\n"
            "1. 9 top-level sections (Services, Data, APIs, Events, Workflows, Security, Scalability, Observability, Reliability)\n"
            "2. Use 2-4 column tables for: entity relationships, endpoints, service responsibilities, workflows, state transitions\n"
            "3. Each bullet: 12-18 words, implementation-focused, no rationale\n"
            "4. NO repeated tech terms across sections (mention Kubernetes once, Redis once)\n"
            "5. NO generic explanations or 'why we do this' preambles\n"
            "6. Focus on WHAT+HOW, not WHY or WHEN\n"
            "7. If approaching size limit: drop subsection descriptions, keep facts only\n"
            "8. Avoid prose; prefer tables, lists, code snippets",
            name="generation_rules",
        )

        .add_system(
            "TECHNICAL DEPTH REQUIREMENTS:\n"
            "Services: Name, responsibilities, ownership boundaries, folder/module layout, repository/service/controller layers, validators, processors, schedulers, event publishers, cache handlers, retry handlers, orchestration modules, auth/state handling\n"
            "Data: Entities + key fields, relationships, indexing strategy, replication/caching, transaction boundaries, optimistic locking, idempotency keys, cache invalidation\n"
            "APIs: Grouped by domain, endpoints with METHOD /path, request purpose, auth requirements, validation rules, pagination, versioning, response/error structure, inter-service contracts, contract examples\n"
            "Events: Queues/topics, publishers/subscribers, async communication patterns, retry policy, DLQ handling, idempotency, consumer groups, ordering, eventual consistency notes\n"
            "Workflows: Service interaction flows, saga patterns, state machines (PENDING → PAID → PREPARING → PICKED_UP → DELIVERED), payment rollback, delivery assignment, notification triggers\n"
            "Security: Auth flow (JWT/mTLS), RBAC rules, rate limiting, encryption at-rest/in-transit, audit logging, service-to-service trust\n"
            "Scalability: Autoscaling triggers, load balancing, connection pooling, async workers, deployment containers, cache scaling, broker partitioning\n"
            "Observability: Log aggregation targets, metrics to track, distributed tracing headers, span correlation, alert thresholds, dashboards\n"
            "Reliability: Retry patterns, circuit breaker config, timeout values, fallback mechanisms, DLQ recovery, consistency guarantees",
            name="depth_requirements",
        )

        .add_system(
            "REDUNDANCY ELIMINATION:\n"
            "- Mention authentication mechanism ONCE in Security section only; do not repeat in APIs or other sections\n"
            "- Mention deployment platform (Kubernetes/Docker) ONCE in Scalability section only\n"
            "- Mention monitoring tools/strategies ONCE in Observability section only\n"
            "- Do not reiterate 'security best practices' or 'architectural principles' across sections\n"
            "- Each section should add NEW implementation details, not recap previous sections\n"
            "- When size approaches limit: cut descriptive text, keep ONLY configuration values and specifics",
            name="redundancy_rules",
        )

        .add_system(
            "OUTPUT FORMATTING FOR ORCHESTRATION:\n"
            "- Use Markdown tables with consistent column counts (3-4 columns per table)\n"
            "- Use code blocks for: config examples, schema snippets, response formats\n"
            "- Use bullet lists for: strategies, thresholds, targets, requirements\n"
            "- AVOID: nested bullet lists (max 1 level of nesting)\n"
            "- AVOID: multi-line descriptions per row; use short phrases or values\n"
            "- All output must be valid Markdown (parseable by downstream systems)\n"
            "- Do not include front matter or metadata; start with # BACKEND LOW-LEVEL DESIGN\n"
            "- Do not pad output with blank lines or spaces. Every character must be meaningful content.",
            name="orchestration_format",
        )

        .add_system(
            "IMPORTANT: Output must contain all 9 required section headings exactly as shown below. "
            "If you reach the character limit, provide concise implementation details for every section; do not omit a heading."
        )

        .add_user(
            "# BACKEND LOW-LEVEL DESIGN\n\n"
            "## 1. Service Architecture\n"
            "## 2. Data Models & Database Design\n"
            "## 3. API Design\n"
            "## 4. Event-Driven Architecture\n"
            "## 5. Workflows & State Transitions\n"
            "## 6. Security & Auth\n"
            "## 7. Scalability & Deployment\n"
            "## 8. Observability\n"
            "## 9. Reliability & Error Handling\n\n"
            "System description:\n{lld_input}".format(lld_input=escaped_input)
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