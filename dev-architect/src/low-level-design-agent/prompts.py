SECTION_EXTRACTION_PROMPT = """Role:
You are a website low-level design engineer.

Goal:
Produce implementation inputs that stay tightly aligned to the exact user goal.

Original User Goal:
{user_goal}

Input Document:
{document}

Requirements Document:
{requirement_doc}

Architecture Document:
{architecture_doc}

Task:
Extract only concrete build requirements from the input.

Output Rules:
- Output Markdown only.
- Start with heading: Website Objective.
- Then provide these headings exactly in order:
	1) Core Sections
	2) Data and Content Requirements
	3) Integration and Styling Requirements
	4) Non-Functional Constraints
- Use short bullet points with actionable statements.
- Keep each bullet specific to the user goal and provided input.
- Do not add strengths, gaps, critiques, missing-items lists, or recommendations.
- Do not invent stack details that are not present in the input.
"""

ARCHITECTURE_ANALYSIS_PROMPT = """Role:
You are a principal engineer converting extracted requirements into implementation decisions.

Original User Goal:
{user_goal}

Input Sections:
{sections}

Requirements Document:
{requirement_doc}

Architecture Document:
{architecture_doc}

Task:
Generate a build-plan document, not a review.

Output Rules:
- Output Markdown only.
- Use this title: Technical Implementation Plan.
- Provide these sections exactly:
	1) Component Assembly Plan
	2) Data Contracts and State Flow
	3) API and Integration Contracts
	4) Rendering, Performance, and Accessibility Decisions
	5) Error Handling and Operational Safeguards
- For each section, provide direct implementation decisions and ordered steps.
- Keep all content grounded in the user goal and input sections.
- Do not use "strengths", "gaps", "missing elements", or audit language.
"""

REPORT_GENERATION_PROMPT = """Role:
You are a senior software architect writing the final implementation-ready low-level design.

Original User Goal:
{user_goal}

Input Plan:
{analysis}

Requirements Document:
{requirement_doc}

Architecture Document:
{architecture_doc}

Task:
Generate the final LLD document that a team can implement directly.

Output Rules:
- Output Markdown only.
- Start with title: # LLD REPORT
- The first content after the title must be an opening block with exactly these 3 labeled paragraphs in order:
	1) Goal Summary:
	2) Scope:
	3) Implementation Focus:
- Each paragraph must be 2 sentences long and together they must fully introduce the document.
- Do not start with generic boilerplate such as "This document outlines..." or "This report describes...".
- Include these sections exactly in order:
	1) Goal Summary and Scope
	2) Final Component Blueprint
	3) Data Models and Interface Schemas
	4) API Endpoints and Validation Rules
	5) Styling, Responsiveness, and SEO Implementation Notes
	6) Failure Handling, Monitoring, and Runbook Notes
- Keep the opening block specific, complete, and tied to the provided user goal.
- The opening block must mention the website type, the implementation target, and the main functional areas covered later in the report.
- Include compact TypeScript interfaces where schemas are required.
- Include numbered implementation steps for critical flows.
- Do not include critique sections or recommendation sections.
- Do not output placeholder text such as "add as needed" or "example".
"""
