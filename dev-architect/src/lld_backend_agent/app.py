"""
app.py – Backend LLD Agent (WITH CONTEXT SUPPORT)
"""

from __future__ import annotations

import logging
import importlib
import sys
import types
from pathlib import Path
from typing import TYPE_CHECKING

from state import LLD_INPUT
from prompts import BACKEND_LLD_PROMPT, BACKEND_LLD_TASK

if TYPE_CHECKING:
    from reusableagents.context import AgentContext


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

    raise ModuleNotFoundError("❌ agent-adk folder not found")


register_agent_adk()


# ---------- Dynamic Imports ----------
ReusableReActAgent = importlib.import_module(
    "reusableagents.agents.react_agent"
).ReusableReActAgent

OutputValidator = importlib.import_module(
    "reusableagents.agents.validator"
).OutputValidator

AgentConfig = importlib.import_module(
    "reusableagents.config.settings"
).AgentConfig

GeminiConfig = importlib.import_module(
    "reusableagents.config.settings"
).GeminiConfig

create_agent_llm = importlib.import_module(
    "reusableagents.llm.gemini"
).create_agent_llm

create_validator_llm = importlib.import_module(
    "reusableagents.llm.gemini"
).create_validator_llm

AgentContext = importlib.import_module(
    "reusableagents.context"
).AgentContext


# ---------- Logging ----------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s – %(message)s",
)
logger = logging.getLogger(__name__)


# ---------- Build Agent ----------
def build_agent(context: "AgentContext | None" = None):
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

    validator = OutputValidator(llm=validator_llm)

    return ReusableReActAgent(
        tools=[],
        llm=agent_llm,
        prompt_builder=BACKEND_LLD_PROMPT,
        validator=validator,
        config=AgentConfig(
            max_react_iterations=5,
            enable_validation=True,
            validation_score_threshold=0.7,
            max_refinement_attempts=2,
        ),
    )


# ---------- RUN FUNCTION (LIKE FRIEND) ----------
def run_backend_lld(
    lld_input: str | None = None,
    context: "AgentContext | None" = None,
) -> str:

    agent = build_agent(context)

    # Resolve input
    if lld_input:
        resolved_input = lld_input
    elif context and isinstance(context.state, dict):
        resolved_input = context.state.get("lld_input", "")
    else:
        resolved_input = ""

    if not resolved_input:
        raise ValueError("LLD input is required")

    # Record start
    if context:
        context.record(
            agent_name="backend_lld_agent",
            event="started",
        )

    # Run agent
    response = agent.run(
        task=BACKEND_LLD_TASK,
        lld_input=resolved_input,
        context=context,   # 🔥 THIS IS KEY
    )

    output = response.output if hasattr(response, "output") else response

    # Save output in context
    if context:
        context.set_state("backend_lld.output", output)
        context.record(
            agent_name="backend_lld_agent",
            event="completed",
        )

    return output


# ---------- MAIN ----------
def main():
    logger.info("Starting Backend LLD Agent")

    # 🔥 CREATE CONTEXT
    context = AgentContext()

    # 🔥 STORE INPUT IN CONTEXT
    context.set_state("lld_input", LLD_INPUT)

    output = run_backend_lld(context=context)

    logger.info("=" * 70)
    logger.info(" GENERATED BACKEND LLD ")
    logger.info("=" * 70)
    logger.info("\n%s\n", output)
    logger.info("=" * 70)


# ---------- RUN ----------
if __name__ == "__main__":
    main()