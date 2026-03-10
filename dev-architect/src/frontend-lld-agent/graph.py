from state import AgentState
from tools_and_schemas import generate_lld


def run_lld_agent(state: AgentState) -> AgentState:

    architecture = state.architecture_text

    lld = generate_lld(architecture)

    state.lld_output = lld

    return state