"""
pp.py – Backend LLD Agent (STRICT GENERATOR MODE)
"""

from __future__ import annotations

import sys
import types
import importlib
import logging
import os
import uuid
from pathlib import Path
from typing import TYPE_CHECKING

logger = logging.getLogger(__name__)

# ============================================================
# ✅ REGISTER ADK
# ============================================================

def register_agent_adk():
    if "reusableagents" in sys.modules:
        return

    base_path = Path(__file__).resolve()

    for i in range(1, 4):
        path = base_path.parents[i] / "agent-adk"
        if path.exists():
            pkg = types.ModuleType("reusableagents")
            pkg.__path__ = [str(path)]
            sys.modules["reusableagents"] = pkg
            return

    raise ModuleNotFoundError("agent-adk folder not found")


register_agent_adk()

# ✅ KEY FIX: import build_backend_lld_prompt instead of BACKEND_LLD_PROMPT
from .prompts import build_backend_lld_prompt, BACKEND_LLD_TASK

if TYPE_CHECKING:
    from reusableagents.context import AgentContext  # type: ignore


# ============================================================
# ✅ LOAD COMPONENTS
# ============================================================

def load_adk_components():
    react_mod   = importlib.import_module("reusableagents.agents.react_agent")
    config_mod  = importlib.import_module("reusableagents.config.settings")
    valid_mod   = importlib.import_module("reusableagents.agents.validator")
    llm_mod     = importlib.import_module("reusableagents.llm.gemini")

    return (
        react_mod.ReusableReActAgent,
        config_mod.AgentConfig,
        valid_mod.OutputValidator,
        config_mod.GeminiConfig,
        llm_mod.create_agent_llm,
        llm_mod.create_validator_llm,
    )


# ============================================================
# ✅ BUILD AGENT
# ✅ KEY FIX: accepts prompt parameter so lld_input is baked in
# ============================================================

def build_agent(prompt):
    (
        ReusableReActAgent,
        AgentConfig,
        OutputValidator,
        GeminiConfig,
        create_agent_llm,
        create_validator_llm,
    ) = load_adk_components()

    gemini_config = GeminiConfig(
        project_id="eds-alchemy",
        location="us-central1",
        agent_model="gemini-2.5-flash-lite",
        validator_model="gemini-2.5-flash-lite",
        agent_temperature=0.0,
        validator_temperature=0.0,
    )

    agent_llm     = create_agent_llm(gemini_config)
    validator_llm = create_validator_llm(gemini_config)
    validator     = OutputValidator(llm=validator_llm)

    enable_validation = str(
        os.getenv("BACKEND_LLD_ENABLE_VALIDATION", "false")
    ).strip().lower() in {"1", "true", "yes", "on"}

    return ReusableReActAgent(
        tools=[],
        llm=agent_llm,
        prompt_builder=prompt,          # ✅ baked-in prompt passed here
        validator=validator,
        config=AgentConfig(
            max_react_iterations=int(os.getenv("BACKEND_LLD_MAX_REACT_ITERATIONS", "2")),
            enable_validation=enable_validation,
            validation_score_threshold=0.5,
            max_refinement_attempts=int(os.getenv("BACKEND_LLD_MAX_REFINEMENT_ATTEMPTS", "1")),
        ),
    )


# ============================================================
# ✅ CREATE CONTEXT
# ============================================================

def create_context(
    user_input: str,
    requirement_doc: str,
    architecture_doc: str | None = None,
) -> "AgentContext":
    from reusableagents.context import AgentContext, SessionInfo

    state = {"user_input": user_input, "requirement_doc": requirement_doc}
    if architecture_doc is not None:
        state["architecture_doc"] = architecture_doc

    return AgentContext(
        session=SessionInfo(session_id=str(uuid.uuid4()), metadata={}),
        state=state,
    )


# ============================================================
# ✅ DEFAULT INPUT
# ============================================================

LLD_INPUT = """
This document provides details for a one-page marketing website built with Next.js.
The website includes hero section, about, services, and contact with Google Maps integration.
Focus on static content, performance, SEO, and responsiveness.
"""


# ============================================================
# ✅ CHUNKING UTILITY
# ============================================================

def chunk_text(text: str, chunk_size: int = 8000, overlap: int = 500) -> list[str]:
    env_chunk_size = str(os.getenv("BACKEND_LLD_CHUNK_SIZE", "")).strip()
    env_overlap = str(os.getenv("BACKEND_LLD_CHUNK_OVERLAP", "")).strip()
    if env_chunk_size:
        try:
            chunk_size = max(2000, int(env_chunk_size))
        except ValueError:
            pass
    if env_overlap:
        try:
            overlap = max(0, int(env_overlap))
        except ValueError:
            pass

    if len(text) <= chunk_size:
        return [text]

    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        if end < len(text):
            for i in range(min(overlap, chunk_size)):
                if end - i > start and text[end - i] in ".!?\n":
                    end = end - i + 1
                    break
            else:
                while end > start and text[end - 1] not in " \t\n":
                    end -= 1
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        start = end - overlap if overlap > 0 else end

    return chunks


def _resolve_lld_input(
    lld_input: str | None = None,
    context: "AgentContext | None" = None,
) -> str:
    # Priority: explicit lld_input param > requirement_doc in context > lld_input in context
    if str(lld_input or "").strip():
        return str(lld_input).strip()

    if isinstance(getattr(context, "state", None), dict):
        # Accept an explicit requirements doc if provided by the caller
        req = str(context.state.get("requirement_doc", "")).strip()
        if req:
            return req

        # Accept system analyst or prior LLD outputs as fallback
        for key in ("lld.output", "system_analyst.output", "system_architect.output", "lld_input"):
            val = str(context.state.get(key, "")).strip()
            if val:
                return val

    return ""


# ============================================================
# ✅ RUN AGENT
# ✅ KEY FIX: build_backend_lld_prompt(chunk) called per chunk
#    so lld_input is always baked into the prompt — no {task}
#    substitution needed or relied upon.
# ============================================================

def run_backend_lld(
    lld_input: str | None = None,
    context: "AgentContext | None" = None,
) -> str:

    resolved_input = _resolve_lld_input(lld_input, context)

    if not resolved_input:
        raise ValueError("lld_input is required")

    chunks = chunk_text(resolved_input, chunk_size=8000, overlap=500)
    outputs = []

    for i, chunk in enumerate(chunks):

        # ✅ Build a fresh prompt with this chunk baked in
        prompt = build_backend_lld_prompt(chunk)

        # ✅ Build a fresh agent with that prompt
        agent = build_agent(prompt)

        # ✅ task string is now just a trigger label — the real
        #    content is already inside the user prompt above
        task_label = (
            f"Generate Backend LLD"
            if len(chunks) == 1
            else f"Generate Backend LLD — part {i + 1} of {len(chunks)}"
        )

        run_kwargs = {
            "task": task_label,
            "state": {"lld_input": chunk},
        }

        if context is not None:
            run_kwargs["context"] = context

        response = agent.run(**run_kwargs)

        output = (
            response.output
            if hasattr(response, "output")
            else str(response)
        )
        outputs.append(output)

    combined = "\n\n---\n\n".join(outputs)

    # Strip accidental review-style words
    blacklist = ["review", "strength", "weakness"]
    for word in blacklist:
        combined = combined.replace(word, "")

    return combined.strip()


# ============================================================
# ✅ MAIN
# ============================================================

def main():
    try:
        output = run_backend_lld(lld_input=LLD_INPUT)
        print(output)
    except Exception:
        logger.exception("Execution failed")
        raise


# ============================================================
# ✅ ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()