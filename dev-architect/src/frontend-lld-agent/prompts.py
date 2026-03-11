LLD_PROMPT_TEMPLATE = """
You are a Senior Software Engineer.

Your task is to convert a System Architecture Document
into a detailed Low Level Design (LLD).

Architecture Document:
{architecture}

Generate the following sections:

1. Module & Component Specifications
2. Component Hierarchy
3. TypeScript Interfaces
4. Data Models
5. Logic and Algorithms
6. API Design
7. Styling System
8. Error Handling

Technology stack:
Next.js
React
TypeScript
TailwindCSS

Output the LLD as a Markdown document.
"""