from dataclasses import dataclass

@dataclass
class AgentState:
    lld_input: str
    backend_output: str = ""