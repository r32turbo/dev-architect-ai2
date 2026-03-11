from state import AgentState
from graph import run_lld_agent


def main():

    state = AgentState(
        architecture_text="Architecture text will come from previous agent"
    )

    result_state = run_lld_agent(state)

    print(result_state.lld_output)


if __name__ == "__main__":
    main()