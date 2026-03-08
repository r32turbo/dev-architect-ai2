"""
System Architecture Agent (Using Groq API)

This program generates a System Architecture Document
from a System Analyst Document.

Project Structure:

system_architecture_agent/
│
├── main.py
├── analyst_document.txt
├── architecture_output.txt
├── .env

---------------------------------------
HOW TO RUN

1. Install dependencies

pip install openai python-dotenv

2. Create .env file

GROQ_API_KEY=your_groq_api_key

3. Put System Analyst document inside

analyst_document.txt

4. Run the program

python main.py

5. Output will be saved in

architecture_output.txt
---------------------------------------
"""

import os
from openai import OpenAI
from dotenv import load_dotenv


# Load environment variables from .env
load_dotenv()

# Get the directory where this script is located
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Create Groq client (OpenAI-compatible API)
client = OpenAI(
    api_key=os.getenv("GROQ_API_KEY"),
    base_url="https://api.groq.com/openai/v1"
)


# ---------------------------------------------
# Read System Analyst Document
# ---------------------------------------------
def read_analyst_document():
    """Reads analyst_document.txt"""

    file_path = os.path.join(SCRIPT_DIR, "analyst_document.txt")
    with open(file_path, "r", encoding="utf-8") as file:
        return file.read()


# ---------------------------------------------
# Create Prompt for the LLM
# ---------------------------------------------
def create_prompt(input_document):
    """Constructs the prompt sent to the LLM"""

    prompt = f"""
You are a System Architecture Agent responsible for designing a system architecture based on the provided System Analyst document.

Analyze the requirement document and generate a structured System Architecture Document.

The output must strictly follow this structure:

Title

Description

Architecture Type

Subsystems

* Subsystem 1
* Subsystem 2
* Subsystem 3

Technology Details (with version number)

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
# Send prompt to Groq LLM
# ---------------------------------------------
def generate_architecture(prompt):
    """Calls Groq API to generate architecture"""

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
# Save Architecture Document
# ---------------------------------------------
def save_architecture_document(output_text):
    """Writes architecture output to architecture_output.txt"""

    file_path = os.path.join(SCRIPT_DIR, "architecture_output.txt")
    with open(file_path, "w", encoding="utf-8") as file:
        file.write(output_text)


# ---------------------------------------------
# Main AI Agent Workflow
# ---------------------------------------------
def main():

    # Step 1: Read analyst document
    analyst_document = read_analyst_document()

    # Step 2: Create prompt
    prompt = create_prompt(analyst_document)

    # Step 3: Generate architecture
    architecture = generate_architecture(prompt)

    # Step 4: Save output
    save_architecture_document(architecture)

    # Step 5: Success message
    print("Architecture Document Generated Successfully")


# Run the program
if __name__ == "__main__":
    main()