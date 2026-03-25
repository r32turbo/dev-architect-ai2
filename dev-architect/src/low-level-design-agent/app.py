import os
import sys
import types
import importlib
from pathlib import Path

from dotenv import load_dotenv
from langchain_google_vertexai import ChatVertexAI
from langgraph.graph import END, START, StateGraph

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
    # Fallback for direct script execution (python app.py).
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
AgentConfig = importlib.import_module("config.settings").AgentConfig
PromptBuilder = importlib.import_module("prompts.base").PromptBuilder


llm = ChatVertexAI(
    model_name=os.getenv("GEMINI_AGENT_MODEL", "gemini-2.5-flash-lite"),
    project=os.getenv("GEMINI_PROJECT_ID", "eds-alchemy"),
    location=os.getenv("GEMINI_LOCATION", "us-central1"),
    temperature=0.0,
)

agent_config = AgentConfig(
    max_react_iterations=5,
    enable_validation=True,
    validation_score_threshold=0.7,
    max_refinement_attempts=2,
)

agent_llm = llm
validator_llm = llm
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


def _run_task(task: str) -> str:
    response = react_agent.run(task=task)
    return response.output if isinstance(response.output, str) else str(response.output)


def extract_sections(state: LLDAgentState) -> dict[str, str]:
    document = state["lld_input"]
    prompt = SECTION_EXTRACTION_PROMPT.format(document=document)
    return {"sections": _run_task(prompt)}


def analyze_architecture(state: LLDAgentState) -> dict[str, str]:
    sections = state["sections"]
    prompt = ARCHITECTURE_ANALYSIS_PROMPT.format(sections=sections)
    return {"architecture_analysis": _run_task(prompt)}


def generate_report(state: LLDAgentState) -> dict[str, str]:
    analysis = state["architecture_analysis"]
    prompt = REPORT_GENERATION_PROMPT.format(analysis=analysis)
    return {"final_report": _run_task(prompt)}


builder = StateGraph(LLDAgentState)

builder.add_node("extract_sections", extract_sections)
builder.add_node("analyze_architecture", analyze_architecture)
builder.add_node("generate_report", generate_report)

builder.add_edge(START, "extract_sections")
builder.add_edge("extract_sections", "analyze_architecture")
builder.add_edge("analyze_architecture", "generate_report")
builder.add_edge("generate_report", END)

graph = builder.compile()


if __name__ == "__main__":
    result = graph.invoke({"lld_input": LLD_INPUT})

    print("\n------ LLD REVIEW REPORT ------\n")
    print(result["final_report"])
