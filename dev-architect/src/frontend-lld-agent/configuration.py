import sys
import types
import importlib
from pathlib import Path


def register_agent_adk() -> None:
    """Expose src/agent-adk as importable package `reusableagents`."""
    if "reusableagents" in sys.modules:
        return
    adk_root = Path(__file__).resolve().parents[1] / "agent-adk"
    pkg = types.ModuleType("reusableagents")
    pkg.__path__ = [str(adk_root)]
    sys.modules["reusableagents"] = pkg
    # Patch broken create_agent import in react_agent.py
    from langgraph.prebuilt import create_react_agent
    from langchain_core.messages import SystemMessage

    def create_agent_patch(model, tools, system_prompt=None, **kwargs):
        if system_prompt:
            return create_react_agent(
                model, tools, prompt=SystemMessage(content=system_prompt), **kwargs
            )
        return create_react_agent(model, tools, **kwargs)

    import langchain.agents as lc_agents
    if not hasattr(lc_agents, "create_agent"):
        lc_agents.create_agent = create_agent_patch


register_agent_adk()

GeminiConfig         = importlib.import_module("reusableagents.config.settings").GeminiConfig
AgentConfig          = importlib.import_module("reusableagents.config.settings").AgentConfig
create_agent_llm     = importlib.import_module("reusableagents.llm.gemini").create_agent_llm
create_validator_llm = importlib.import_module("reusableagents.llm.gemini").create_validator_llm