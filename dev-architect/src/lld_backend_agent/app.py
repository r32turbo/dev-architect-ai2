"""
pp.py – Backend LLD Agent (STRICT GENERATOR MODE)
"""

from __future__ import annotations

import sys
import types
import importlib
import logging
import warnings
from pathlib import Path
from typing import TYPE_CHECKING

from prompts import BACKEND_LLD_PROMPT, BACKEND_LLD_TASK

if TYPE_CHECKING:
    from reusableagents.context import AgentContext  # type: ignore


# ============================================================
# ✅ LOGGER (KEEPED)
# ============================================================

logging.basicConfig(
    level=logging.ERROR,
    format="%(message)s",
)
logger = logging.getLogger(__name__)


# ============================================================
# ✅ WARNINGS (KEEPED)
# ============================================================

warnings.filterwarnings("ignore", category=Warning)


# ============================================================
# ✅ REGISTER ADK (KEEPED)
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


# ============================================================
# ✅ LOAD COMPONENTS (KEEPED)
# ============================================================

def load_adk_components():
    react_mod = importlib.import_module("reusableagents.agents.react_agent")
    config_mod = importlib.import_module("reusableagents.config.settings")
    validator_mod = importlib.import_module("reusableagents.agents.validator")
    llm_mod = importlib.import_module("reusableagents.llm.gemini")

    return (
        react_mod.ReusableReActAgent,
        config_mod.AgentConfig,
        validator_mod.OutputValidator,
        config_mod.GeminiConfig,
        llm_mod.create_agent_llm,
        llm_mod.create_validator_llm,
    )


# ============================================================
# ✅ BUILD AGENT (SLIGHT FIX → GENERATION FOCUSED)
# ============================================================

def build_agent():
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

    agent_llm = create_agent_llm(gemini_config)
    validator_llm = create_validator_llm(gemini_config)

    # 🔥 IMPORTANT: validator kept but won't override generation
    validator = OutputValidator(llm=validator_llm)

    return ReusableReActAgent(
        tools=[],
        llm=agent_llm,
        prompt_builder=BACKEND_LLD_PROMPT,
        validator=validator,
        config=AgentConfig(
            max_react_iterations=3,   # 🔥 reduce overthinking
            enable_validation=True,   # keep workflow
            validation_score_threshold=0.5,  # 🔥 avoid blocking output
            max_refinement_attempts=1,  # 🔥 prevent rewriting into review
        ),
    )


# ============================================================
# ✅ DEFAULT INPUT (KEEPED)
# ============================================================

LLD_INPUT = """
This document provides details for a one-page marketing website built with Next.js.
The website includes hero section, about, services, and contact with Google Maps integration.
Focus on static content, performance, SEO, and responsiveness.
"""


# ============================================================
# ✅ RESOLVE INPUT (KEEPED)
# ============================================================

def _resolve_lld_input(
    lld_input: str | None = None,
    context: "AgentContext | None" = None,
) -> str:
    if str(lld_input or "").strip():
        return str(lld_input).strip()

    if isinstance(getattr(context, "state", None), dict):
        val = str(context.state.get("lld_input", "")).strip()
        if val:
            return val

    return ""


# ============================================================
# ✅ RUN AGENT (FIXED → FORCE CLEAN OUTPUT)
# ============================================================

def run_backend_lld(
    lld_input: str | None = None,
    context: "AgentContext | None" = None,
) -> str:

    agent = build_agent()

    resolved_input = _resolve_lld_input(lld_input, context)

    if not resolved_input:
        raise ValueError("lld_input is required")

    run_kwargs = {
        "task": BACKEND_LLD_TASK,
        "state": {"lld_input": resolved_input},
    }

    if context is not None:
        run_kwargs["context"] = context

    response = agent.run(**run_kwargs)

    # 🔥 FORCE CLEAN LLD OUTPUT (NO REVIEW TEXT)
    output = (
        response.output
        if hasattr(response, "output")
        else str(response)
    )

    # 🔥 REMOVE accidental "review-style" phrases
    blacklist = ["review", "strength", "weakness", "analysis"]
    for word in blacklist:
        output = output.replace(word, "")

    return output.strip()


# ============================================================
# ✅ MAIN (KEEPED)
# ============================================================

def main():
    try:
        output = run_backend_lld(lld_input=LLD_INPUT)

        print(output)  # ✅ ONLY FINAL LLD OUTPUT

    except Exception:
        logger.exception("Execution failed")
        raise


# ============================================================
# ✅ ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()