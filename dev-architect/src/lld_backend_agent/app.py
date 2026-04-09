"""
app.py – Entry point for Backend LLD Agent
"""

from __future__ import annotations

import logging
import importlib
import sys
import types
from pathlib import Path

from state import LLD_INPUT
from prompts import BACKEND_LLD_PROMPT, BACKEND_LLD_TASK


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


# ---------- Logging ----------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s – %(message)s",
)
logger = logging.getLogger(__name__)


# ---------- Configure LLM ----------
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


# ---------- Agent Config ----------
agent_config = AgentConfig(
    max_react_iterations=5,
    enable_validation=True,
    validation_score_threshold=0.7,
    max_refinement_attempts=2,
)

validator = OutputValidator(
    llm=validator_llm,
    score_threshold=agent_config.validation_score_threshold,
)


# ---------- Agent ----------
react_agent = ReusableReActAgent(
    tools=[],
    llm=agent_llm,
    prompt_builder=BACKEND_LLD_PROMPT,
    validator=validator,
    config=agent_config,
)


# ---------- Main ----------
def main() -> None:

    print("\n Backend LLD Agent")
    print("─" * 40)

    task = BACKEND_LLD_TASK

    # ✅ FIXED: Proper context passing
    response = react_agent.run(
        task=task,
        lld_input=LLD_INPUT
    )

    output = (
        response.output
        if isinstance(response.output, str)
        else str(response.output)
    )

    logger.info("=" * 70)
    logger.info(" GENERATED BACKEND LLD ")
    logger.info("=" * 70)
    logger.info("\n%s\n", output)
    logger.info("=" * 70)


# ---------- Run ----------
if __name__ == "__main__":
    main()