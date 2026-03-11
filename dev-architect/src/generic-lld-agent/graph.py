from state import AgentState
from tools_and_schemas import generate_lld


def run_lld_agent(state: AgentState) -> AgentState:
    
    # Read input from state
    lld_text = state.lld_document

    # Generate Generic LLD
    generic_lld = generate_lld(lld_text)

    # Save output in state
    state.lld_output = generic_lld

    return state