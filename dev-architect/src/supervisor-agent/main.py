"""
Supervisor Agent: Orchestrates System Analyst and Low-Level Design Agents.

This agent manages the workflow:
1. User Goal -> System Analyst Agent -> System Requirements
2. System Requirements -> LLD Agent -> LLD Report
"""

import os
import sys
import types
import importlib
import importlib.util
import warnings
from pathlib import Path
from typing import TypedDict

from dotenv import load_dotenv
from langgraph.graph import StateGraph, START, END

try:
    from langchain_google_vertexai import ChatVertexAI
except ImportError:
    ChatVertexAI = None  # type: ignore

# Hide known ChatVertexAI deprecation warnings
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

# ============ SETUP PATHS AND IMPORTS ============

ADK_ROOT = Path(__file__).resolve().parents[1] / "agent-adk"
if str(ADK_ROOT) not in sys.path:
    sys.path.insert(0, str(ADK_ROOT))

SUPERVISOR_ROOT = Path(__file__).resolve().parent
SYSTEM_ANALYST_ROOT = Path(__file__).resolve().parents[1] / "system-analyst-agent"
LLD_AGENT_ROOT = Path(__file__).resolve().parents[1] / "low-level-design-agent"

# Load environment early
load_dotenv()

# Import supervisor-specific modules first (use absolute imports to avoid conflicts)
sup_state_spec = importlib.util.spec_from_file_location("supervisor_state", SUPERVISOR_ROOT / "state.py")
supervisor_state_mod = importlib.util.module_from_spec(sup_state_spec)
sup_state_spec.loader.exec_module(supervisor_state_mod)
SupervisorState = supervisor_state_mod.SupervisorState  # type: ignore

sup_prompts_spec = importlib.util.spec_from_file_location("supervisor_prompts", SUPERVISOR_ROOT / "prompts.py")
supervisor_prompts_mod = importlib.util.module_from_spec(sup_prompts_spec)
sup_prompts_spec.loader.exec_module(supervisor_prompts_mod)
HANDOFF_PROMPT = supervisor_prompts_mod.HANDOFF_PROMPT  # type: ignore

# Import system analyst prompt
sa_prompt_spec = importlib.util.spec_from_file_location("system_analyst_prompt", SYSTEM_ANALYST_ROOT / "prompt.py")
sa_prompt_mod = importlib.util.module_from_spec(sa_prompt_spec)
sa_prompt_spec.loader.exec_module(sa_prompt_mod)
SYSTEM_ANALYST_PROMPT = sa_prompt_mod.SYSTEM_ANALYST_PROMPT  # type: ignore

# Import LLD agent modules using sys.path
if str(LLD_AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(LLD_AGENT_ROOT))

try:
    from app import graph as lld_graph  # type: ignore
except ImportError:
    lld_graph = None

# ============ LOAD ADK COMPONENTS ============

def load_adk_components():
    """Load reusable agent components from ADK."""
    react_mod = importlib.import_module("reusableagents.agents.react_agent")
    prompts_mod = importlib.import_module("reusableagents.prompts.base")
    config_mod = importlib.import_module("reusableagents.config.settings")
    validator_mod = importlib.import_module("reusableagents.agents.validator")
    return (
        react_mod.ReusableReActAgent,
        prompts_mod.PromptBuilder,
        config_mod.AgentConfig,
        validator_mod.OutputValidator,
    )


def _register_agent_adk_package() -> None:
    """Expose src/agent-adk as importable package name `reusableagents`."""
    if "reusableagents" in sys.modules:
        return

    adk_root = Path(__file__).resolve().parents[1] / "agent-adk"
    reusableagents_pkg = types.ModuleType("reusableagents")
    reusableagents_pkg.__path__ = [str(adk_root)]
    sys.modules["reusableagents"] = reusableagents_pkg


# Register ADK package alias
_register_agent_adk_package()


# ============ ENVIRONMENT & LLM SETUP ============

def load_environment():
    """Load environment from .env file."""
    for path in [Path.cwd(), *Path.cwd().parents]:
        env_file = path / ".env"
        if env_file.exists():
            load_dotenv(env_file)
            break


def create_llm(model: str):
    """Create ChatVertexAI LLM instance."""
    if ChatVertexAI is None:
        raise ImportError(
            "langchain-google-vertexai is required for supervisor agent. "
            "Install it with: pip install langchain-google-vertexai"
        )
    
    return ChatVertexAI(
        model_name=model,
        project=os.getenv("GOOGLE_CLOUD_PROJECT", "eds-alchemy"),
        location=os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1"),
        temperature=0.0,
        max_output_tokens=8192,
    )


# ============ AGENT BUILDERS ============

def build_system_analyst_agent():
    """Build the system analyst agent."""
    ReusableReActAgent, PromptBuilder, AgentConfig, OutputValidator = load_adk_components()
    
    llm = create_llm(os.getenv("GEMINI_AGENT_MODEL", "gemini-2.5-flash-lite"))
    validator_llm = create_llm(os.getenv("GEMINI_VALIDATOR_MODEL", "gemini-2.5-flash-lite"))
    
    validator = OutputValidator(llm=validator_llm)
    
    prompt_builder = (
        PromptBuilder()
        .add_system(SYSTEM_ANALYST_PROMPT)
        .add_user("{user_goal}")
    )
    
    return ReusableReActAgent(
        tools=[],
        llm=llm,
        prompt_builder=prompt_builder,
        validator=validator,
        config=AgentConfig(
            max_react_iterations=5,
            enable_validation=True,
            max_refinement_attempts=2,
        ),
    )


def build_lld_handoff_agent():
    """Build a helper agent to convert system analyst output to LLD input."""
    ReusableReActAgent, PromptBuilder, AgentConfig, OutputValidator = load_adk_components()
    
    llm = create_llm(os.getenv("GEMINI_AGENT_MODEL", "gemini-2.5-flash-lite"))
    validator_llm = create_llm(os.getenv("GEMINI_VALIDATOR_MODEL", "gemini-2.5-flash-lite"))
    
    validator = OutputValidator(llm=validator_llm)
    
    prompt_builder = (
        PromptBuilder()
        .add_system("You are a software architect preparing low-level design inputs.")
        .add_user("{handoff_prompt}")
    )
    
    return ReusableReActAgent(
        tools=[],
        llm=llm,
        prompt_builder=prompt_builder,
        validator=validator,
        config=AgentConfig(
            max_react_iterations=3,
            enable_validation=True,
            max_refinement_attempts=1,
        ),
    )


# ============ GRAPH NODES ============

def system_analyst_node(state: SupervisorState) -> dict:
    """Execute system analyst agent."""
    print("\n[Supervisor] --> Running System Analyst Agent...")
    result = system_analyst_agent.run(user_goal=state["user_goal"])
    output = result.output if hasattr(result, 'output') else str(result)
    
    print(f"[Supervisor] <-- System Analyst Output received ({len(output)} chars)")
    
    return {"system_analyst_output": output}


def handoff_node(state: SupervisorState) -> dict:
    """Convert system analyst output to LLD input format."""
    print("\n[Supervisor] --> Preparing LLD input from system analyst output...")
    
    handoff_prompt = HANDOFF_PROMPT.format(
        system_analysis=state["system_analyst_output"]
    )
    
    result = lld_handoff_agent.run(handoff_prompt=handoff_prompt)
    lld_input = result.output if hasattr(result, 'output') else str(result)
    
    print(f"[Supervisor] <-- LLD input prepared ({len(lld_input)} chars)")
    
    return {"lld_input": lld_input}


def lld_agent_node(state: SupervisorState) -> dict:
    """Execute LLD agent."""
    print("\n[Supervisor] --> Running Low-Level Design Agent...")
    
    if lld_graph is None:
        print("[Supervisor] WARNING: LLD graph not available, skipping LLD execution")
        return {
            "lld_sections": "",
            "lld_architecture_analysis": "",
            "lld_final_report": "LLD agent unavailable",
        }
    
    # Prepare input for LLD graph
    lld_input = state.get("lld_input", state.get("system_analyst_output", ""))
    
    try:
        lld_result = lld_graph.invoke({
            "lld_input": lld_input,
            "sections": "",
            "architecture_analysis": "",
            "final_report": "",
        })
        
        print(f"[Supervisor] <-- LLD Agent execution complete")
        
        return {
            "lld_sections": lld_result.get("sections", ""),
            "lld_architecture_analysis": lld_result.get("architecture_analysis", ""),
            "lld_final_report": lld_result.get("final_report", ""),
        }
    except Exception as e:
        print(f"[Supervisor] ERROR in LLD execution: {e}")
        return {
            "lld_sections": "",
            "lld_architecture_analysis": "",
            "lld_final_report": f"Error: {str(e)}",
        }


def finalize_node(state: SupervisorState) -> dict:
    """Finalize and compose output from both agents."""
    print("\n[Supervisor] --> Finalizing output...")
    
    final_output = f"""
# COMPLETE SYSTEM DESIGN REPORT

## Executive Summary
User Goal: {state["user_goal"]}

---

## PHASE 1: SYSTEM ANALYSIS

{state["system_analyst_output"]}

---

## PHASE 2: LOW-LEVEL DESIGN

### LLD Sections
{state["lld_sections"]}

### Architecture Analysis
{state["lld_architecture_analysis"]}

### Final LLD Report
{state["lld_final_report"]}

---

**Generated by Supervisor Agent (System Analyst + LLD Agent)**
"""
    
    print(f"[Supervisor] <-- Final output composed ({len(final_output)} chars)")
    
    return {"final_output": final_output}


# ============ BUILD GRAPH ============

def build_supervisor_graph():
    """Build the supervisor orchestration graph."""
    graph = StateGraph(SupervisorState)
    
    # Add nodes
    graph.add_node("system_analyst", system_analyst_node)
    graph.add_node("handoff", handoff_node)
    graph.add_node("lld_agent", lld_agent_node)
    graph.add_node("finalize", finalize_node)
    
    # Define edges
    graph.add_edge(START, "system_analyst")
    graph.add_edge("system_analyst", "handoff")
    graph.add_edge("handoff", "lld_agent")
    graph.add_edge("lld_agent", "finalize")
    graph.add_edge("finalize", END)
    
    return graph.compile()


# ============ MAIN ============

def main():
    """Main entry point for supervisor agent."""
    load_environment()
    
    global system_analyst_agent, lld_handoff_agent
    
    print("[Supervisor] Initializing agents...")
    system_analyst_agent = build_system_analyst_agent()
    lld_handoff_agent = build_lld_handoff_agent()
    
    supervisor_app = build_supervisor_graph()
    
    # Example user goal - can be customized
    user_goal = "Create a one-page marketing website using NextJS with contact form, services showcase, and call-to-action buttons."
    
    print(f"\n[Supervisor] Starting orchestration with goal: {user_goal}")
    print("=" * 80)
    
    result = supervisor_app.invoke({
        "user_goal": user_goal,
        "system_analyst_output": "",
        "lld_sections": "",
        "lld_architecture_analysis": "",
        "lld_final_report": "",
        "final_output": "",
    })
    
    print("\n" + "=" * 80)
    print("[Supervisor] Orchestration complete!")
    print("=" * 80)
    
    # Output final result
    if result.get("final_output"):
        print(result["final_output"])
    else:
        print("[ERROR] No final output generated")


if __name__ == "__main__":
    main()
