from pathlib import Path
from typing import TypedDict

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from langchain_groq import ChatGroq
from langgraph.graph import END, START, StateGraph

try:
    from .prompts import (
        ARCHITECTURE_ANALYSIS_PROMPT,
        REPORT_GENERATION_PROMPT,
        SECTION_EXTRACTION_PROMPT,
    )
except ImportError:
    # Fallback for direct script execution (python app.py).
    from prompts import (
        ARCHITECTURE_ANALYSIS_PROMPT,
        REPORT_GENERATION_PROMPT,
        SECTION_EXTRACTION_PROMPT,
    )

load_dotenv()


llm = ChatGroq(
    model="llama-3.3-70b-versatile",
    temperature=0,
)


class AgentState(TypedDict):
    lld_document: str
    sections: str
    architecture_analysis: str
    final_report: str


def extract_sections(state: AgentState) -> dict[str, str]:
    document = state["lld_document"]
    prompt = SECTION_EXTRACTION_PROMPT.format(document=document)
    response = llm.invoke([HumanMessage(content=prompt)])
    return {"sections": response.content}


def analyze_architecture(state: AgentState) -> dict[str, str]:
    sections = state["sections"]
    prompt = ARCHITECTURE_ANALYSIS_PROMPT.format(sections=sections)
    response = llm.invoke([HumanMessage(content=prompt)])
    return {"architecture_analysis": response.content}


def generate_report(state: AgentState) -> dict[str, str]:
    analysis = state["architecture_analysis"]
    prompt = REPORT_GENERATION_PROMPT.format(analysis=analysis)
    response = llm.invoke([HumanMessage(content=prompt)])
    return {"final_report": response.content}


builder = StateGraph(AgentState)

builder.add_node("extract_sections", extract_sections)
builder.add_node("analyze_architecture", analyze_architecture)
builder.add_node("generate_report", generate_report)

builder.add_edge(START, "extract_sections")
builder.add_edge("extract_sections", "analyze_architecture")
builder.add_edge("analyze_architecture", "generate_report")
builder.add_edge("generate_report", END)

graph = builder.compile()


if __name__ == "__main__":
    project_root = Path(__file__).resolve().parents[2]
    input_file = project_root / "lld_input.md"

    if not input_file.exists():
        raise FileNotFoundError(
            f"Input file not found: {input_file}. Create lld_input.md in project root."
        )

    with open(input_file, "r", encoding="utf-8") as file:
        lld_doc = file.read()

    result = graph.invoke({"lld_document": lld_doc})

    print("\n------ LLD REVIEW REPORT ------\n")
    print(result["final_report"])
