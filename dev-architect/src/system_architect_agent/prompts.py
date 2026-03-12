def create_prompt(input_document):

    return f"""
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