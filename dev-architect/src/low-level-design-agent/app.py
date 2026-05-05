from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from langchain_groq import ChatGroq
from langgraph.graph import END, START, StateGraph

try:
    from .state import LLDAgentState, LLD_INPUT
except ImportError:
    from state import LLDAgentState, LLD_INPUT

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


def extract_sections(state: LLDAgentState) -> dict[str, str]:
    document = state["lld_input"]
    safe_document = document.replace("{", "{{").replace("}", "}}") if isinstance(document, str) else document
    prompt = SECTION_EXTRACTION_PROMPT.format(document=safe_document)
    response = llm.invoke([HumanMessage(content=prompt)])
    return {"sections": response.content}


def analyze_architecture(state: LLDAgentState) -> dict[str, str]:
    sections = state["sections"]
    safe_sections = sections.replace("{", "{{").replace("}", "}}") if isinstance(sections, str) else sections
    prompt = ARCHITECTURE_ANALYSIS_PROMPT.format(sections=safe_sections)
    response = llm.invoke([HumanMessage(content=prompt)])
    return {"architecture_analysis": response.content}


def generate_report(state: LLDAgentState) -> dict[str, str]:
    analysis = state["architecture_analysis"]
    safe_analysis = analysis.replace("{", "{{").replace("}", "}}") if isinstance(analysis, str) else analysis
    prompt = REPORT_GENERATION_PROMPT.format(analysis=safe_analysis)
    response = llm.invoke([HumanMessage(content=prompt)])
    return {"final_report": response.content}


builder = StateGraph(LLDAgentState)

builder.add_node("extract_sections", extract_sections)
builder.add_node("analyze_architecture", analyze_architecture)
builder.add_node("generate_report", generate_report)

builder.add_edge(START, "extract_sections")
builder.add_edge("extract_sections", "analyze_architecture")
builder.add_edge("analyze_architecture", "generate_report")
builder.add_edge("generate_report", END)

graph = builder.compile()


if __name__ == "__main__":
    result = graph.invoke({"lld_input": LLD_INPUT})

    print("\n------ LLD REVIEW REPORT ------\n")
    print(result["final_report"])
