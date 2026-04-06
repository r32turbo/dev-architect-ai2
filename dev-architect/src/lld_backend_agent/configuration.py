"""
configuration.py
Registers agent-adk as reusableagents package
"""

import sys
import types
from pathlib import Path
import importlib


def register_agent_adk():
    if "reusableagents" in sys.modules:
        return

    adk_root = Path(__file__).resolve().parents[1] / "agent-adk"

    pkg = types.ModuleType("reusableagents")
    pkg.__path__ = [str(adk_root)]
    sys.modules["reusableagents"] = pkg


# Register once
register_agent_adk()

# Load config
AgentConfig = importlib.import_module(
    "reusableagents.config.settings"
).AgentConfig