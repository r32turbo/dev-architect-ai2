from typing import TypedDict


class LLDAgentState(TypedDict):
    lld_input: str
    sections: str
    architecture_analysis: str
    final_report: str


LLD_INPUT = """Provide a low-level design document to review."""
