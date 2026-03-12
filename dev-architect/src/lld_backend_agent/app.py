from configuration import get_llm
from prompts import SYSTEM_PROMPT


LLD_INPUT = """
# Low Level Design (LLD) Document

Introduction:
This document provides a detailed Low Level Design (LLD) for a one-page marketing website built using Next.js.

Modules:
Navigation
Hero
About
Services
Location / Contact
Footer

Technology Stack:
Next.js
React
TypeScript
Tailwind CSS
Node.js
Google Maps Embed API
"""


def run_backend_lld_agent():

    print("Running Backend LLD Agent...\n")

    client = get_llm()

    completion = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": LLD_INPUT},
        ],
    )

    result = completion.choices[0].message.content

    print("\n===== GENERATED BACKEND LLD =====\n")
    print(result)


if __name__ == "__main__":
    run_backend_lld_agent()