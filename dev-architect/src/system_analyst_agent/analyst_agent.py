import os
import sys
import types
import importlib
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any
from dotenv import load_dotenv

if TYPE_CHECKING:
    from reusableagents.context import AgentContext  # type: ignore[reportMissingImports]

try:
    from .prompts import SYSTEM_ANALYST_PROMPT
except ImportError:
    from prompts import SYSTEM_ANALYST_PROMPT  # type: ignore[reportMissingImports]

ADK_ROOT = Path(__file__).resolve().parents[1] / "agent-adk"
if str(ADK_ROOT) not in sys.path:
    sys.path.insert(0, str(ADK_ROOT))

if "reusableagents" not in sys.modules:
    reusableagents_pkg = types.ModuleType("reusableagents")
    reusableagents_pkg.__path__ = [str(ADK_ROOT)]
    sys.modules["reusableagents"] = reusableagents_pkg

logger = logging.getLogger(__name__)


def load_adk_components():
    react_mod = importlib.import_module("reusableagents.agents.react_agent")
    prompts_mod = importlib.import_module("reusableagents.prompts.base")
    config_mod = importlib.import_module("reusableagents.config.settings")
    validator_mod = importlib.import_module("reusableagents.agents.validator")
    llm_mod = importlib.import_module("reusableagents.llm.gemini")
    return (
        react_mod.ReusableReActAgent,
        prompts_mod.PromptBuilder,
        config_mod.AgentConfig,
        validator_mod.OutputValidator,
        config_mod.GeminiConfig,
        llm_mod.create_agent_llm,
        llm_mod.create_validator_llm,
    )


# ---------------- ENV ----------------
def load_environment():
    base_dir = Path(__file__).resolve().parent
    search_roots = [base_dir, *base_dir.parents, Path.cwd(), *Path.cwd().parents]
    seen: set[Path] = set()

    for path in search_roots:
        resolved = path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        env_file = path / ".env"
        if env_file.exists():
            load_dotenv(env_file)
            break


# ---------------- AGENT SETUP ----------------
def build_agent(context: "AgentContext | None" = None):
    (
        ReusableReActAgent,
        PromptBuilder,
        AgentConfig,
        OutputValidator,
        GeminiConfig,
        create_agent_llm,
        create_validator_llm,
    ) = load_adk_components()

    gemini_config = GeminiConfig(
        project_id=os.getenv("GOOGLE_CLOUD_PROJECT", "eds-alchemy"),
        location=os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1"),
        agent_model=os.getenv("GEMINI_AGENT_MODEL", "gemini-2.5-flash-lite"),       # Primary ReAct agent model
        validator_model=os.getenv("GEMINI_VALIDATOR_MODEL", "gemini-2.5-flash-lite"),   # Separate validator model (can differ)
        agent_temperature=0.0,
        validator_temperature=0.0,
    )

    agent_llm = create_agent_llm(gemini_config)
    validator_llm = create_validator_llm(gemini_config)

    validator = OutputValidator(llm=validator_llm)

    # Resolve optional supporting documents from provided context so prompts can use them
    requirement_doc = ""
    architecture_doc = ""
    if context is not None:
        ctx_state = getattr(context, "state", None)
        if isinstance(ctx_state, dict):
            requirement_doc = str(ctx_state.get("requirement_doc", "")).strip()
            architecture_doc = str(ctx_state.get("architecture_doc", "")).strip()

    # Format the system prompt with the supporting documents while preserving the
    # `{user_goal}` placeholder for the user turn (use double braces in prompt to escape).
    system_prompt = SYSTEM_ANALYST_PROMPT.format(
        requirement_doc=requirement_doc,
        architecture_doc=architecture_doc,
    )

    prompt_builder = (
        PromptBuilder()
        .add_system(system_prompt)
        .add_user("{user_goal}")
    )

    return ReusableReActAgent(
        tools=[],
        llm=agent_llm,
        prompt_builder=prompt_builder,
        validator=validator,
        config=AgentConfig(
            max_react_iterations=5,
            enable_validation=False,
            max_refinement_attempts=2,
        ),
    )


def _resolve_user_goal(
    user_goal: str | None = None,
    context: "AgentContext | None" = None,
) -> str:
    if str(user_goal or "").strip():
        return str(user_goal).strip()
    if isinstance(getattr(context, "state", None), dict):
        goal = str(context.state.get("user_goal", "")).strip()
        if goal:
            return goal
    return ""


def run_system_analysis(
    user_goal: str | None = None,
    context: "AgentContext | None" = None,
) -> str:
    """Run the analyst workflow with optional shared context."""
    load_environment()
    agent = build_agent(context)
    resolved_goal = _resolve_user_goal(user_goal=user_goal, context=context)
    if not resolved_goal:
        raise ValueError("user_goal is required (directly or via context.state['user_goal'])")
    if context is not None and isinstance(getattr(context, "state", None), dict):
        context.state.setdefault("user_goal", resolved_goal)

    result = agent.run(user_goal=resolved_goal, context=context)
    output = str(result.output if hasattr(result, "output") else result).strip()

    if context is not None and callable(getattr(context, "set_state", None)):
        context.set_state("system_analyst.output", output)
    if context is not None and callable(getattr(context, "record", None)):
        context.record(agent_name="system_analyst_agent", event="completed")

    return output


# ---------------- MAIN ----------------
def main():
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    logger.info("Starting system analyst standalone run")
    load_environment()

    user_goal = "Create a one page marketing website using NextJS ."
    logger.info("Executing analyst run")
    output = run_system_analysis(user_goal=user_goal)

    if output:
        logger.info("System analyst run completed successfully")
        print(output)
    else:
        logger.warning("System analyst produced no output")
        print("No output generated.")


if __name__ == "__main__":
    main()