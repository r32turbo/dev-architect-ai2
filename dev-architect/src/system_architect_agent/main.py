import os
from openai import OpenAI
from dotenv import load_dotenv

# Load .env variables
load_dotenv()

# Create Groq client
client = OpenAI(
    api_key=os.getenv("GROQ_API_KEY"),
    base_url="https://api.groq.com/openai/v1"
)

# ---------------------------------------------
# SYSTEM ANALYST INPUT DOCUMENT (EMBEDDED)
# ---------------------------------------------

ANALYST_DOCUMENT = """
# System Analyst Output Document
## One-Page Marketing Website (Next.js)

Description

The objective is to build a simple one-page marketing website using Next.js.

The website will function as a digital landing page that introduces the business, explains services offered, and provides location and contact details.

Website Sections

- Hero Section
- About Section
- Services Section
- Location / Contact Section

Functional Requirements

Hero Section
- Headline
- Subheadline
- CTA button

About Section
- Company description

Services Section
- Minimum 3 services
- Maximum 6 services

Location / Contact Section
- Address
- Phone
- Email
- Google Map

Content Source

All content will be static.

Non Functional Requirements

- Fast loading
- Responsive design
- SEO optimized

System Constraints

- Next.js must be used
- Single page layout

Subsystem

Website
"""


# ---------------------------------------------
# CREATE PROMPT
# ---------------------------------------------

def create_prompt(input_document):

    prompt = f"""
You are a System Architecture Agent.

Analyze the provided System Analyst document and generate a System Architecture Document.

The output must follow this structure:

Title

Description

Architecture Type

Subsystems

* Subsystem 1

Technology Details (with version numbers)

* Technology 1
* Technology 2
* Technology 3

Technical Constraints

* Constraint 1
* Constraint 2
* Constraint 3

System Analyst Document:

{input_document}
"""

    return prompt


# ---------------------------------------------
# GENERATE ARCHITECTURE USING GROQ
# ---------------------------------------------

def generate_architecture(prompt):

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": "You are an expert system architect."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.3
    )

    return response.choices[0].message.content


# ---------------------------------------------
# MAIN WORKFLOW
# ---------------------------------------------

def main():

    print("Running System Architect Agent...\n")

    prompt = create_prompt(ANALYST_DOCUMENT)

    architecture = generate_architecture(prompt)

    print("\n========== SYSTEM ARCHITECTURE OUTPUT ==========\n")
    print(architecture)


if __name__ == "__main__":
    main()