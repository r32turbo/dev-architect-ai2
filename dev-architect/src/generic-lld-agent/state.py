from dataclasses import dataclass
from typing import Optional

@dataclass
class AgentState:
    lld_document: str
    lld_output: Optional[str] = None