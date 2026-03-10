from state import AgentState
from utils import read_file, write_file
from graph import run_lld_agent


def main():

    architecture = read_file("architecture.md")

    state = AgentState(
        architecture_text=architecture
    )

    result_state = run_lld_agent(state)

    write_file(
        "lld_output.md",
        result_state.lld_output
    )

    print("LLD Generated Successfully!")


if __name__ == "__main__":
    main()