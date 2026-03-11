from state import AgentState
from graph import run_lld_agent

def main():
    # Simulated input from previous LLD agent
    state = AgentState(
        lld_document="""
# Low Level Design (LLD)

## Module & Component Specifications
- User module
- Payment module

## Data Models
- User: id, name, email
- Payment: id, user_id, amount

## Logic & Algorithms
- Payment processing logic
"""
    )

    # Run the Generic LLD agent
    result_state = run_lld_agent(state)

    # Print output stored in state
    print("Generated Generic LLD:\n")
    print(result_state.lld_output)  # <- make sure this line exists

if __name__ == "__main__":
    main()