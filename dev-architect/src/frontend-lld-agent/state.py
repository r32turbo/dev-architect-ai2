from dataclasses import dataclass
from typing import Optional

@dataclass
class AgentState:
    architecture_text: str
    lld_output: Optional[str] = None