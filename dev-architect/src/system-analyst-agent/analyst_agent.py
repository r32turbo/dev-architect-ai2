import os
import sys
import importlib
import logging
import warnings
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from prompt import SYSTEM_ANALYST_PROMPT

# Hide known ChatVertexAI deprecation warnings from terminal output.
warnings.filterwarnings(
    "ignore",
    message=r".*ChatVertexAI.*deprecated.*",
    category=Warning,
)
warnings.filterwarnings(
    "ignore",
    message=r".*Use \[`ChatGoogleGenerativeAI`\].*",
    category=Warning,
)

ADK_ROOT = Path(__file__).resolve().parents[1] / "agent-adk"
if str(ADK_ROOT) not in sys.path:
    sys.path.insert(0, str(ADK_ROOT))

logger = logging.getLogger(__name__)


def load_adk_components():
    react_mod = importlib.import_module("agents.react_agent")
    prompts_mod = importlib.import_module("prompts.base")
    config_mod = importlib.import_module("config.settings")
    validator_mod = importlib.import_module("agents.validator")
    llm_mod = importlib.import_module("llm.gemini")
    return (
        react_mod.ReusableReActAgent,
        prompts_mod.PromptBuilder,
        config_mod.AgentConfig,
        validator_mod.OutputValidator,
        config_mod.GeminiConfig,
        llm_mod.create_agent_llm,
        llm_mod.create_validator_llm,
    )


REQUIRED_SECTIONS = [
    "introduction",
    "project goal",
    "scope",
    "functional requirements",
    "non functional requirements",
    "assumptions",
    "out of scope",
    "acceptance criteria",
    "risks and mitigations",
]


def normalize_text(text: str) -> str:
    return "".join(ch if ch.isalnum() or ch.isspace() else " " for ch in text.lower())


def deduplicate_output(text: str) -> str:
    """Remove repeated markdown chunks while preserving order and spacing."""
    if not text.strip():
        return text

    chunks = [chunk.strip() for chunk in text.split("\n\n") if chunk.strip()]
    seen = set()
    unique_chunks = []

    for chunk in chunks:
        normalized_chunk = " ".join(normalize_text(chunk).split())
        if normalized_chunk and normalized_chunk not in seen:
            seen.add(normalized_chunk)
            unique_chunks.append(chunk)

    return "\n\n".join(unique_chunks).strip()


def normalize_analyst_output(text: str) -> str:
    """Normalize analyst output into clean markdown without conversational preamble."""
    raw = str(text or "").strip()
    if not raw:
        return ""

    lines = raw.splitlines()
    first_heading_idx = next(
        (i for i, line in enumerate(lines) if line.strip().startswith("#")),
        None,
    )

    if first_heading_idx is not None and first_heading_idx > 0:
        raw = "\n".join(lines[first_heading_idx:]).strip()
    elif first_heading_idx is None:
        raw = (
            "## System Requirements and Design Specification\n\n"
            f"{raw}"
        )

    return raw


# ---------------- ENV ----------------
def load_environment():
    for path in [Path.cwd(), *Path.cwd().parents]:
        env_file = path / ".env"
        if env_file.exists():
            load_dotenv(env_file)
            break


# ---------------- AGENT SETUP ----------------
def build_agent():
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

    prompt_builder = (
        PromptBuilder()
        .add_system(SYSTEM_ANALYST_PROMPT)
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


def run_system_analysis(user_goal: str, context: Any = None) -> str:
    """Run the analyst workflow with optional shared context."""
    load_environment()
    agent = build_agent()

    if context is not None and callable(getattr(context, "record", None)):
        context.record(
            agent_name="system_analyst_agent",
            event="started",
            detail=str(user_goal)[:160],
        )

    run_kwargs = {"user_goal": user_goal}
    if context is not None:
        run_kwargs["context"] = context

    result = agent.run(**run_kwargs)
    output = normalize_analyst_output(result.output if hasattr(result, "output") else result)

    output = deduplicate_output(output)

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