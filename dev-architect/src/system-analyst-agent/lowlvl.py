import os
from typing import TypedDict
from pathlib import Path
from langgraph.graph import StateGraph, START, END
from langchain_core.messages import HumanMessage
from langchain_groq import ChatGroq
from dotenv import load_dotenv

load_dotenv()

# Initialize LLM
llm = ChatGroq(
    model="llama-3.3-70b-versatile",
    temperature=0
)


# -------------------------
# Agent State
# -------------------------

class AgentState(TypedDict):
    lld_document: str
    sections: str
    architecture_analysis: str
    final_report: str


# -------------------------
# Node 1: Section Extractor
# -------------------------

def extract_sections(state: AgentState):

    document = state["lld_document"]

    prompt = f"""
Persona:
You are a Senior Software Architect specializing in
software design documentation.

Context:
You are given a Low Level Design (LLD) document that
describes a software system. The document may contain
sections such as introduction, modules, component
hierarchy, data models, APIs, and technology stack.

Task:
Identify and extract the major architectural sections
from the document.

Input Document:
{document}

Constraints:
- Return structured sections
- Use bullet points
- Keep the content concise

Example Output:

Introduction:
Brief overview of the system.

Modules:
Presentation Layer
Business Logic Layer
Data Layer

Component Hierarchy:
App → Navigation → Services → Footer
"""

    response = llm.invoke([HumanMessage(content=prompt)])

    return {"sections": response.content}


# -------------------------
# Node 2: Architecture Analysis
# -------------------------

def analyze_architecture(state: AgentState):

    sections = state["sections"]

    prompt = f"""
Persona:
You are a Principal Software Architect performing
a technical design review.

Context:
The following sections were extracted from a Low
Level Design document of a software system.

Task:
Analyze the architecture and evaluate:

1. Component structure
2. Data model design
3. API integration
4. Technology stack suitability
5. System scalability

Input Sections:
{sections}

Constraints:
- Focus on architectural quality
- Identify strengths and weaknesses
- Provide technical reasoning

Example:

Component Analysis:
The architecture separates UI components from
data models, improving maintainability.
"""

    response = llm.invoke([HumanMessage(content=prompt)])

    return {"architecture_analysis": response.content}


# -------------------------
# Node 3: Final Report Generator
# -------------------------

def generate_report(state: AgentState):

    analysis = state["architecture_analysis"]

    prompt = f"""
Persona:
You are a Senior Software Architecture Reviewer.

Context:
An architecture analysis of a Low Level Design
document has been completed.

Task:
Generate a structured LLD Review Report.

Input Analysis:
{analysis}

Constraints:
- Output must be in Markdown
- Use clear headings
- Provide actionable improvement suggestions

Output Structure:

# LLD Review Report

## Document Overview

## Module and Component Analysis

## Architecture Quality Assessment

## Data Model Evaluation

## API Design Review

## Technology Stack Evaluation

## Missing Elements

## Improvement Recommendations

Example:

## Data Model Evaluation
The Service model correctly encapsulates
service-related attributes.
"""

    response = llm.invoke([HumanMessage(content=prompt)])

    return {"final_report": response.content}


# -------------------------
# Build LangGraph
# -------------------------

builder = StateGraph(AgentState)

builder.add_node("extract_sections", extract_sections)
builder.add_node("analyze_architecture", analyze_architecture)
builder.add_node("generate_report", generate_report)

builder.add_edge(START, "extract_sections")
builder.add_edge("extract_sections", "analyze_architecture")
builder.add_edge("analyze_architecture", "generate_report")
builder.add_edge("generate_report", END)

graph = builder.compile()


# -------------------------
# Run Agent
# -------------------------

if __name__ == "__main__":

    # Get the script's directory and construct path to input file
    script_dir = Path(__file__).parent.parent.parent
    input_file = script_dir / "lld_input.md"
    
    with open(input_file, "r") as f:
        lld_doc = f.read()

    result = graph.invoke({
        "lld_document": lld_doc
    })

    print("\n------ LLD REVIEW REPORT ------\n")
    print(result["final_report"])