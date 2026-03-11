from configuration import client, MODEL_NAME
from prompts import LLD_PROMPT_TEMPLATE


def generate_lld(architecture_text: str):

    prompt = LLD_PROMPT_TEMPLATE.format(
        architecture=architecture_text
    )

    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {
                "role": "system",
                "content": "You are an expert software engineer."
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        temperature=0.2
    )

    return response.choices[0].message.content