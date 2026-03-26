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
    import langchain.agents as lc_agents
    if not hasattr(lc_agents, "create_agent"):
        lc_agents.create_agent = create_react_agent


register_agent_adk()

AgentConfig = importlib.import_module("reusableagents.config.settings").AgentConfig