from typing import TypedDict


class SupervisorState(TypedDict):
    user_goal: str
    system_analyst_output: str
    lld_sections: str
    lld_architecture_analysis: str
    lld_final_report: str
    final_output: str
