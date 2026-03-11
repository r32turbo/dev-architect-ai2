from .configuration import get_client
from .prompts import create_prompt


def run_architect_agent(state):

    client = get_client()

    prompt = create_prompt(state.analyst_document)

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": "You are an expert system architect."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.3
    )

    state.architecture_output = response.choices[0].message.content

    return state