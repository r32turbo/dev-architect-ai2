from typing import TypedDict


class SupervisorState(TypedDict):
    """State managed by the supervisor agent orchestrating system analysis and LLD."""
    
    # Input from user
    user_goal: str
    
    # Output from system analyst agent
    system_analyst_output: str
    
    # Intermediate outputs from LLD agent
    lld_sections: str
    lld_architecture_analysis: str
    
    # Final outputs
    lld_final_report: str
    final_output: str
