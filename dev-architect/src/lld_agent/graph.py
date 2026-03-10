from state import AgentState
from tools_and_schemas import generate_lld


def run_lld_agent(state: AgentState) -> AgentState:

    lld = generate_lld(state.architecture_text)

    state.lld_output = lld

    return state