from configuration import client, MODEL_NAME
from prompts import build_prompt, backend_lld_prompt, get_current_date
from state import AgentState


def run_backend_lld_agent(state: AgentState):
    # Build the prompt using the template with current date and LLD document
    prompt = build_prompt(
        backend_lld_prompt,
        current_date=get_current_date(),
        lld_document=state.lld_input
    )

    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": "You are a backend architecture expert."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.3
    )

    state.backend_output = response.choices[0].message.content

    return state