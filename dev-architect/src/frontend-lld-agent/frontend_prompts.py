"""
prompts.py
PromptBuilder for the Frontend LLD Agent.

Prompt structure:
  WHO   - role/persona of the agent
  WHAT  - the task it must perform
  WHY   - context and purpose
  HOW   - desired output format
  RULES - constraints and boundaries
  WITH  - input data (user section, dynamic)
"""
import importlib

# register_agent_adk() is already called in graph.py before this file loads
PromptBuilder = importlib.import_module("reusableagents.prompts.base").PromptBuilder


FRONTEND_LLD_PROMPT = (
    PromptBuilder()

    # WHO
    .add_system(
        "You are a senior frontend architect translating architecture into precise frontend LLD specs.",
        name="persona",
    )

    # WHAT + WHY
    .add_system(
        "Task: Generate a concise Frontend Low-Level Design (LLD) document.\n\n"
        "Context: Define exact frontend architecture, component structure, state management, API integration, responsive behavior, and realtime delivery tracking UX.\n"
        "Focus only on UI-layer engineering; ignore backend service implementation details, data persistence, queues, and transaction logic.",
        name="task_and_context",
    )

    # HOW
    .add_system(
        "Output Format:\n"
        "Write in Markdown with exact sections and compact bullets. Use tables, component trees, and code blocks.\n"
        "Keep the document under 9000 characters. Do not describe backend service internals.\n\n"
        "## Frontend LLD\n\n"
        "### 1. UI Component Architecture\n\n"
        "List components, props, children, and render boundaries.\n\n"
        "### 2. Routing & Navigation\n\n"
        "Define routes, guards, and nested layouts.\n\n"
        "### 3. State Management\n\n"
        "Define stores, local state, caching, and WebSocket state flows.\n\n"
        "### 4. API Integration Contracts\n\n"
        "List endpoints, payloads, auth scope, and error handling.\n\n"
        "### 5. Responsive & Performance Design\n\n"
        "Define breakpoints, rendering strategy, and lazy loading.\n\n"
        "### 6. Error Handling & UX Edge Cases\n\n"
        "List failure UI states, fallback flows, and notifications.",
        name="output_format",
    )

    # RULES
    .add_system(
        "Constraints:\n"
        "- Use only provided inputs.\n"
        "- Complete sections, no placeholders.\n"
        "- Use TypeScript code blocks and markdown tables.\n"
        "- Do not include backend folder structure, transaction logic, or event broker details.\n"
        "- Prefer structured bullets, tables, and code blocks over narrative.\n"
        "- Treat architecture_doc as a compact integration summary when available.",
        name="constraints",
    )

    # WITH
    .add_user(
        "## User Request\n{user_input}\n\n## Requirements\n{requirement_doc}\n\n## Architecture\n{architecture_doc}",
        name="input_data",
    )
)