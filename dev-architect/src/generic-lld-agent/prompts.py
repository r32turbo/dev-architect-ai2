LLD_PROMPT_TEMPLATE = """
You are a Senior Software Engineer and Software Architect.

Your task is to convert the given Low Level Design (LLD) document
into a **Generic Low Level Design (GLLD)** that can be reused
across different systems and technology stacks.

The generated design must be **technology-agnostic and domain-neutral**.

Important Rules:
- Remove project-specific details.
- Do NOT mention specific technologies (e.g., MySQL, Java, Apache, Stripe, Next.js, etc.).
- Do NOT assume a specific business domain (e.g., payments, ecommerce, healthcare).
- Replace domain-specific modules with generic ones such as:
  Resource Module, Transaction Module, User Module, Service Module, etc.
- Use generic terms like:
  - Relational Database
  - Application Server
  - External Service
  - Backend Service
  - REST API
- Focus on **design patterns, architecture structure, and system logic**.
- The design should be reusable for many applications.

LLD Document:
{lld_document}

Generate the following sections:

## 1. Module & Component Specifications
Describe system modules and their internal components in a generic way.

## 2. Data Models & Schema
Define reusable data models and their relationships without referencing a specific database technology.

## 3. Detailed Logic & Algorithms
Explain the workflows and algorithms in an abstract, implementation-independent way.

## 4. Integration & Interface Design
Describe APIs and external integrations using generic REST-style interfaces.

## 5. System Constraints & Configuration
Describe system configuration in a technology-agnostic manner.

## 6. Error Handling & Edge Cases
Explain how the system should handle failures, invalid input, and unexpected scenarios.

Output the final Generic Low Level Design as a **well-structured Markdown document**.
"""