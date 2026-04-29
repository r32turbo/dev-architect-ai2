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

# Hide known ChatVertexAI deprecation warnings from terminal output.
warnings.filterwarnings(
    "ignore",
    message=r".*ChatVertexAI.*deprecated.*",
    category=DeprecationWarning,
)
warnings.filterwarnings(
    "ignore",
    message=r".*Use \[`ChatGoogleGenerativeAI`\].*",
    category=DeprecationWarning,
)
warnings.filterwarnings(
    "ignore",
    message=r".*langchain-google-genai.*ChatGoogleGenerativeAI.*",
    category=DeprecationWarning,
)
try:
    from langchain_core._api.deprecation import LangChainDeprecationWarning

    warnings.filterwarnings("ignore", category=LangChainDeprecationWarning)
except Exception:
    pass

try:
    from .state import LLDAgentState, LLD_INPUT
except ImportError:
    current_dir = Path(__file__).resolve().parent
    state_spec = importlib.util.spec_from_file_location(
        "low_level_design_state", current_dir / "state.py"
    )
    if state_spec is None or state_spec.loader is None:
        raise RuntimeError("Unable to load local state.py")
    state_module = importlib.util.module_from_spec(state_spec)
    state_spec.loader.exec_module(state_module)
    LLDAgentState = state_module.LLDAgentState
    LLD_INPUT = state_module.LLD_INPUT

try:
    from .prompts import (
        ARCHITECTURE_ANALYSIS_PROMPT,
        REPORT_GENERATION_PROMPT,
        SECTION_EXTRACTION_PROMPT,
    )
except ImportError:
    # Fallback for direct script execution (python lld_createagent.py).
    current_dir = Path(__file__).resolve().parent
    prompts_spec = importlib.util.spec_from_file_location(
        "low_level_design_prompts", current_dir / "prompts.py"
    )
    if prompts_spec is None or prompts_spec.loader is None:
        raise RuntimeError("Unable to load local prompts.py")
    prompts_module = importlib.util.module_from_spec(prompts_spec)
    prompts_spec.loader.exec_module(prompts_module)
    ARCHITECTURE_ANALYSIS_PROMPT = prompts_module.ARCHITECTURE_ANALYSIS_PROMPT
    REPORT_GENERATION_PROMPT = prompts_module.REPORT_GENERATION_PROMPT
    SECTION_EXTRACTION_PROMPT = prompts_module.SECTION_EXTRACTION_PROMPT

load_dotenv()

logger = logging.getLogger(__name__)


def _get_chunking_config() -> tuple[int, int]:
    chunk_size = int(os.getenv("LLD_CHUNK_SIZE_CHARS", "12000"))
    chunk_overlap = int(os.getenv("LLD_CHUNK_OVERLAP_CHARS", "1200"))
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

        # Prefer cutting at a paragraph or line boundary to keep chunks coherent.
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


def _merge_chunk_outputs(
    stage_name: str,
    outputs: list[str],
    context: "AgentContext | None" = None,
) -> str:
    cleaned_outputs = [str(item).strip() for item in outputs if str(item).strip()]
    if not cleaned_outputs:
        return ""
    if len(cleaned_outputs) == 1:
        return cleaned_outputs[0]

    merged_source = "\n\n".join(
        f"### {stage_name} Chunk {idx + 1}\n{item}"
        for idx, item in enumerate(cleaned_outputs)
    )
    merge_prompt = (
        f"Original user goal: {_resolve_user_goal(context=context)}\n"
        "You MUST keep the merged output aligned with this exact goal and domain.\n\n"
        f"You are merging outputs from multiple {stage_name} chunks. "
        "Combine them into one coherent result, remove duplicates, keep important details, "
        "and preserve clear markdown structure.\n\n"
        f"Chunk outputs:\n\n{merged_source}"
    )
    return _run_task(merge_prompt, context=context)


def _resolve_user_goal(
    context: "AgentContext | None" = None,
    state: dict[str, str] | None = None,
) -> str:
    if context is not None:
        ctx_state = getattr(context, "state", None)
        if isinstance(ctx_state, dict):
            goal = str(ctx_state.get("user_goal", "")).strip()
            if goal:
                return goal

    if isinstance(state, dict):
        raw_input = str(state.get("lld_input", "")).strip()
        if raw_input:
            first_line = raw_input.splitlines()[0].strip()
            return first_line[:200]

    return "Unknown goal"


def _resolve_lld_docs(
    context: "AgentContext | None" = None,
    state: dict[str, str] | None = None,
) -> tuple[str, str]:
    requirement_doc = ""
    architecture_doc = ""

    if context is not None:
        ctx_state = getattr(context, "state", None)
        if isinstance(ctx_state, dict):
            requirement_doc = str(ctx_state.get("requirement_doc", "")).strip()
            architecture_doc = str(ctx_state.get("architecture_doc", "")).strip()

    if isinstance(state, dict):
        requirement_doc = requirement_doc or str(state.get("requirement_doc", "")).strip()
        architecture_doc = architecture_doc or str(state.get("architecture_doc", "")).strip()

    return requirement_doc, architecture_doc


def _register_agent_adk_package() -> None:
    """Expose src/agent-adk as importable package name `reusableagents`."""
    if "reusableagents" in sys.modules:
        return

    adk_root = Path(__file__).resolve().parents[1] / "agent-adk"
    if str(adk_root) not in sys.path:
        sys.path.insert(0, str(adk_root))

    reusableagents_pkg = types.ModuleType("reusableagents")
    reusableagents_pkg.__path__ = [str(adk_root)]
    sys.modules["reusableagents"] = reusableagents_pkg


_register_agent_adk_package()

ReusableReActAgent = importlib.import_module(
    "reusableagents.agents.react_agent"
).ReusableReActAgent
OutputValidator = importlib.import_module(
    "reusableagents.agents.validator"
).OutputValidator
settings_mod = importlib.import_module("reusableagents.config.settings")
AgentConfig = settings_mod.AgentConfig
GeminiConfig = settings_mod.GeminiConfig
PromptBuilder = importlib.import_module("reusableagents.prompts.base").PromptBuilder
llm_mod = importlib.import_module("reusableagents.llm.gemini")
create_agent_llm = llm_mod.create_agent_llm
create_validator_llm = llm_mod.create_validator_llm


gemini_config = GeminiConfig(
    project_id=os.getenv("GEMINI_PROJECT_ID", "eds-alchemy"),
    location=os.getenv("GEMINI_LOCATION", "us-central1"),
    agent_model=os.getenv("GEMINI_AGENT_MODEL", "gemini-2.5-flash-lite"),       # Primary ReAct agent model
    validator_model=os.getenv("GEMINI_AGENT_MODEL", "gemini-2.5-flash-lite"),   # Separate validator model (can differ)
    agent_temperature=0.0,
    validator_temperature=0.0,
)

agent_config = AgentConfig(
    max_react_iterations=5,
    enable_validation=True,
    validation_score_threshold=0.7,
    max_refinement_attempts=2,
)

agent_llm = create_agent_llm(gemini_config)
validator_llm = create_validator_llm(gemini_config)
validator = OutputValidator(
    llm=validator_llm,
    score_threshold=agent_config.validation_score_threshold,
)

react_prompt = (
    PromptBuilder()
    .add_system(
        "You are a precise low-level design generator for a one-page marketing website. "
        "Follow the task exactly and return only the requested output.",
        name="persona",
    )
    .add_user("{task}", name="task")
)

react_agent = ReusableReActAgent(
    tools=[],
    llm=agent_llm,
    prompt_builder=react_prompt,
    validator=validator,
    config=agent_config,
)

fallback_agent_config = AgentConfig(
    max_react_iterations=agent_config.max_react_iterations,
    enable_validation=False,
    max_refinement_attempts=agent_config.max_refinement_attempts,
)

fallback_react_agent = ReusableReActAgent(
    tools=[],
    llm=agent_llm,
    prompt_builder=react_prompt,
    validator=validator,
    config=fallback_agent_config,
)


def _run_task(task: str, context: "AgentContext | None" = None) -> str:
    run_kwargs = {"task": task}
    if context is not None:
        run_kwargs["context"] = context

    try:
        response = react_agent.run(**run_kwargs)
    except AttributeError as exc:
        # Known edge case: validator returns None and crashes score access.
        if "'NoneType' object has no attribute 'score'" not in str(exc):
            raise
        logger.warning("Validation path failed, retrying task with fallback agent")
        response = fallback_react_agent.run(**run_kwargs)
    return response.output if isinstance(response.output, str) else str(response.output)


def extract_sections(
    state: dict[str, str],
    context: "AgentContext | None" = None,
) -> dict[str, str]:
    logger.info("LLD stage: extract_sections")
    document = state["lld_input"]
    user_goal = _resolve_user_goal(context=context, state=state)
    requirement_doc, architecture_doc = _resolve_lld_docs(context=context, state=state)
    chunk_size, chunk_overlap = _get_chunking_config()
    doc_chunks = _chunk_text(document, chunk_size=chunk_size, chunk_overlap=chunk_overlap)

    if len(doc_chunks) > 1:
        logger.info("LLD extract_sections chunking enabled (%d chunks)", len(doc_chunks))

    chunk_outputs: list[str] = []
    for idx, chunk in enumerate(doc_chunks):
        prompt = SECTION_EXTRACTION_PROMPT.format(
            document=chunk,
            user_goal=user_goal,
            requirement_doc=requirement_doc,
            architecture_doc=architecture_doc,
        )
        result = _run_task(prompt, context=context)
        chunk_outputs.append(result)
        if context is not None and callable(getattr(context, "set_state", None)):
            context.set_state(f"lld.sections.chunk_{idx + 1}", result)

    output = _merge_chunk_outputs("section extraction", chunk_outputs, context=context)
    if context is not None and callable(getattr(context, "set_state", None)):
        context.set_state("lld.sections", output)
    return {"sections": output}


def analyze_architecture(
    state: dict[str, str],
    context: "AgentContext | None" = None,
) -> dict[str, str]:
    logger.info("LLD stage: analyze_architecture")
    sections = state["sections"]
    user_goal = _resolve_user_goal(context=context, state=state)
    requirement_doc, architecture_doc = _resolve_lld_docs(context=context, state=state)
    chunk_size, chunk_overlap = _get_chunking_config()
    section_chunks = _chunk_text(sections, chunk_size=chunk_size, chunk_overlap=chunk_overlap)

    if len(section_chunks) > 1:
        logger.info("LLD analyze_architecture chunking enabled (%d chunks)", len(section_chunks))

    chunk_outputs: list[str] = []
    for idx, chunk in enumerate(section_chunks):
        prompt = ARCHITECTURE_ANALYSIS_PROMPT.format(
            sections=chunk,
            user_goal=user_goal,
            requirement_doc=requirement_doc,
            architecture_doc=architecture_doc,
        )
        result = _run_task(prompt, context=context)
        chunk_outputs.append(result)
        if context is not None and callable(getattr(context, "set_state", None)):
            context.set_state(f"lld.architecture_analysis.chunk_{idx + 1}", result)

    output = _merge_chunk_outputs("architecture analysis", chunk_outputs, context=context)
    if context is not None and callable(getattr(context, "set_state", None)):
        context.set_state("lld.architecture_analysis", output)
    return {"architecture_analysis": output}


def generate_report(
    state: dict[str, str],
    context: "AgentContext | None" = None,
) -> dict[str, str]:
    logger.info("LLD stage: generate_report")
    analysis = state["architecture_analysis"]
    user_goal = _resolve_user_goal(context=context, state=state)
    requirement_doc, architecture_doc = _resolve_lld_docs(context=context, state=state)
    chunk_size, chunk_overlap = _get_chunking_config()
    analysis_chunks = _chunk_text(analysis, chunk_size=chunk_size, chunk_overlap=chunk_overlap)

    if len(analysis_chunks) > 1:
        logger.info("LLD generate_report chunking enabled (%d chunks)", len(analysis_chunks))

    chunk_outputs: list[str] = []
    for idx, chunk in enumerate(analysis_chunks):
        prompt = REPORT_GENERATION_PROMPT.format(
            analysis=chunk,
            user_goal=user_goal,
            requirement_doc=requirement_doc,
            architecture_doc=architecture_doc,
        )
        result = _run_task(prompt, context=context)
        chunk_outputs.append(result)
        if context is not None and callable(getattr(context, "set_state", None)):
            context.set_state(f"lld.final_report.chunk_{idx + 1}", result)

    output = _merge_chunk_outputs("final report", chunk_outputs, context=context)
    if context is not None and callable(getattr(context, "set_state", None)):
        context.set_state("lld.final_report", output)
    return {"final_report": output}


def run_pipeline(
    lld_input: str,
    requirement_doc: str = "",
    architecture_doc: str = "",
    context: "AgentContext | None" = None,
) -> dict[str, str]:
    logger.info("Starting LLD standalone pipeline")
    if context is not None and callable(getattr(context, "record", None)):
        context.record(agent_name="lld_agent", event="started", detail=str(lld_input)[:160])

    state = {
        "lld_input": lld_input,
        "requirement_doc": requirement_doc,
        "architecture_doc": architecture_doc,
    }
    state.update(extract_sections(state, context=context))
    state.update(analyze_architecture(state, context=context))
    state.update(generate_report(state, context=context))

    if context is not None and callable(getattr(context, "set_state", None)):
        context.set_state(
            "lld.output",
            {
                "sections": str(state.get("sections", "")).strip(),
                "architecture_analysis": str(state.get("architecture_analysis", "")).strip(),
                "final_report": str(state.get("final_report", "")).strip(),
            },
        )
    if context is not None and callable(getattr(context, "record", None)):
        context.record(agent_name="lld_agent", event="completed")

    logger.info("LLD standalone pipeline completed")
    return {
        "sections": str(state.get("sections", "")).strip(),
        "architecture_analysis": str(state.get("architecture_analysis", "")).strip(),
        "final_report": str(state.get("final_report", "")).strip(),
    }


if __name__ == "__main__":
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    result = run_pipeline(LLD_INPUT)

    print("\n------ LLD REPORT ------\n")
    print(result["final_report"])
