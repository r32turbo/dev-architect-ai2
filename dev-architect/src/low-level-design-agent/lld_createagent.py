import os
import sys
import types
import importlib
import logging
import warnings
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

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
    "agents.react_agent"
).ReusableReActAgent
OutputValidator = importlib.import_module(
    "agents.validator"
).OutputValidator
settings_mod = importlib.import_module("config.settings")
AgentConfig = settings_mod.AgentConfig
GeminiConfig = settings_mod.GeminiConfig
PromptBuilder = importlib.import_module("prompts.base").PromptBuilder
llm_mod = importlib.import_module("llm.gemini")
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
        "You are a precise low-level design review assistant. "
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


def _run_task(task: str, context: Any = None) -> str:
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


def extract_sections(state: dict[str, str], context: Any = None) -> dict[str, str]:
    logger.info("LLD stage: extract_sections")
    document = state["lld_input"]
    prompt = SECTION_EXTRACTION_PROMPT.format(document=document)
    output = _run_task(prompt, context=context)
    if context is not None and callable(getattr(context, "set_state", None)):
        context.set_state("lld.sections", output)
    return {"sections": output}


def analyze_architecture(state: dict[str, str], context: Any = None) -> dict[str, str]:
    logger.info("LLD stage: analyze_architecture")
    sections = state["sections"]
    prompt = ARCHITECTURE_ANALYSIS_PROMPT.format(sections=sections)
    output = _run_task(prompt, context=context)
    if context is not None and callable(getattr(context, "set_state", None)):
        context.set_state("lld.architecture_analysis", output)
    return {"architecture_analysis": output}


def generate_report(state: dict[str, str], context: Any = None) -> dict[str, str]:
    logger.info("LLD stage: generate_report")
    analysis = state["architecture_analysis"]
    prompt = REPORT_GENERATION_PROMPT.format(analysis=analysis)
    output = _run_task(prompt, context=context)
    if context is not None and callable(getattr(context, "set_state", None)):
        context.set_state("lld.final_report", output)
    return {"final_report": output}


def run_pipeline(lld_input: str, context: Any = None) -> dict[str, str]:
    logger.info("Starting LLD standalone pipeline")
    if context is not None and callable(getattr(context, "record", None)):
        context.record(agent_name="lld_agent", event="started", detail=str(lld_input)[:160])

    state = {"lld_input": lld_input}
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

    print("\n------ LLD REVIEW REPORT ------\n")
    print(result["final_report"])
