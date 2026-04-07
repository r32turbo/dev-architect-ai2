import os
import sys
import types
import importlib
import logging
import warnings
from pathlib import Path
from typing import TYPE_CHECKING, Any

from dotenv import load_dotenv

if TYPE_CHECKING:
    from reusableagents.context import AgentContext  # type: ignore[reportMissingImports]

try:
    from .prompt import SYSTEM_ANALYST_PROMPT
except ImportError:
    from prompt import SYSTEM_ANALYST_PROMPT  # type: ignore[reportMissingImports]

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

if "reusableagents" not in sys.modules:
    reusableagents_pkg = types.ModuleType("reusableagents")
    reusableagents_pkg.__path__ = [str(ADK_ROOT)]
    sys.modules["reusableagents"] = reusableagents_pkg

logger = logging.getLogger(__name__)


def _get_chunking_config() -> tuple[int, int]:
    chunk_size = int(os.getenv("SYSTEM_ANALYST_CHUNK_SIZE_CHARS", "8000"))
    chunk_overlap = int(os.getenv("SYSTEM_ANALYST_CHUNK_OVERLAP_CHARS", "800"))
    if chunk_size < 1000:
        chunk_size = 1000
    if chunk_overlap < 0:
        chunk_overlap = 0
    if chunk_overlap >= chunk_size:
        chunk_overlap = max(0, chunk_size // 10)
    return chunk_size, chunk_overlap


def _chunk_text(text: str, chunk_size: int, chunk_overlap: int) -> list[str]:
    source = str(text or "")
    if len(source) <= chunk_size:
        return [source]

    chunks: list[str] = []
    start = 0
    text_len = len(source)

    while start < text_len:
        end = min(start + chunk_size, text_len)
        if end < text_len:
            paragraph_break = source.rfind("\n\n", start, end)
            line_break = source.rfind("\n", start, end)
            break_at = paragraph_break if paragraph_break > start else line_break
            if break_at > start:
                end = break_at

        part = source[start:end].strip()
        if part:
            chunks.append(part)

        if end >= text_len:
            break
        start = max(end - chunk_overlap, start + 1)

    return chunks or [source]


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

    if context is not None and callable(getattr(context, "record", None)):
        context.record(
            agent_name="system_analyst_agent",
            event="started",
            detail=str(resolved_goal)[:160],
        )
    chunk_size, chunk_overlap = _get_chunking_config()
    goal_chunks = _chunk_text(resolved_goal, chunk_size=chunk_size, chunk_overlap=chunk_overlap)

    if len(goal_chunks) > 1:
        logger.info("System analyst chunking enabled (%d chunks)", len(goal_chunks))

    chunk_outputs: list[str] = []
    for idx, chunk in enumerate(goal_chunks):
        run_kwargs = {
            "user_goal": (
                f"Original goal:\n{resolved_goal}\n\n"
                f"Analyze this goal chunk ({idx + 1}/{len(goal_chunks)}):\n{chunk}"
            )
            if len(goal_chunks) > 1
            else resolved_goal
        }
        if context is not None:
            run_kwargs["context"] = context

        result = agent.run(**run_kwargs)
        out = normalize_analyst_output(result.output if hasattr(result, "output") else result)
        chunk_outputs.append(out)
        if context is not None and callable(getattr(context, "set_state", None)):
            context.set_state(f"system_analyst.output.chunk_{idx + 1}", out)

    output = deduplicate_output("\n\n".join(item for item in chunk_outputs if str(item).strip()))

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