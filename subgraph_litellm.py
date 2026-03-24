import os
from pathlib import Path
from typing import TypedDict

import litellm
from dotenv import load_dotenv
from langgraph.graph import END, START, StateGraph


env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=env_path)

USE_VERTEX = os.getenv("USE_VERTEX", "true").lower() == "true"

if USE_VERTEX:
    litellm.vertex_project = os.getenv("GOOGLE_CLOUD_PROJECT", "eds-alchemy")
    litellm.vertex_location = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
    MODEL_NAME = os.getenv("LITELLM_MODEL", "gemini-2.0-flash-lite-001")
else:
    MODEL_NAME = os.getenv("LITELLM_MODEL", "gemini-2.0-flash-lite-001")


class State(TypedDict):
    question: str
    supervisor_prompt: str
    research_data: str
    final_answer: str


def call_llm(messages: list[dict[str, str]]) -> str:
    if not USE_VERTEX:
        gemini_api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not gemini_api_key:
            raise ValueError(
                "Set GEMINI_API_KEY (or GOOGLE_API_KEY) when USE_VERTEX=false."
            )

    response = litellm.completion(
        model=MODEL_NAME,
        messages=messages,
        temperature=0.7,
    )
    return response["choices"][0]["message"]["content"]


def research_node(state: State):
    question = state["question"]
    supervisor_prompt = state["supervisor_prompt"]

    research_prompt = (
        "You are an expert AI research agent. "
        "Explain modern AI tools accurately. "
        "LangGraph is a framework by LangChain for multi-agent workflows. "
        "Provide clear factual bullet points."
    )

    response = call_llm(
        [
            {"role": "system", "content": research_prompt},
            {
                "role": "user",
                "content": f"Supervisor Instructions:\n{supervisor_prompt}\n\nUser Question:\n{question}",
            },
        ]
    )

    print("Research Agent working...")
    return {"research_data": response}


research_builder = StateGraph(State)
research_builder.add_node("research_node", research_node)
research_builder.add_edge(START, "research_node")
research_builder.add_edge("research_node", END)
research_subgraph = research_builder.compile()


def summarize_node(state: State):
    research = state["research_data"]
    question = state["question"]
    supervisor_prompt = state["supervisor_prompt"]

    print("Summarizer Agent working...")

    summary_prompt = (
        "You are the summarizer agent. Give a direct answer first, then key points."
    )

    response = call_llm(
        [
            {"role": "system", "content": summary_prompt},
            {
                "role": "user",
                "content": f"{supervisor_prompt}\n\nQuestion:\n{question}\n\nResearch:\n{research}",
            },
        ]
    )

    return {"final_answer": response}


summary_builder = StateGraph(State)
summary_builder.add_node("summarize_node", summarize_node)
summary_builder.add_edge(START, "summarize_node")
summary_builder.add_edge("summarize_node", END)
summary_subgraph = summary_builder.compile()


def supervisor_node(state: State):
    print("Supervisor received question:", state["question"])

    supervisor_prompt = (
        "Role: Supervisor Agent\n"
        "1. Extract relevant facts only\n"
        "2. Avoid hallucination\n"
        "3. Answer first, then points\n"
        "4. Keep concise"
    )

    return {"supervisor_prompt": supervisor_prompt}


builder = StateGraph(State)
builder.add_node("supervisor", supervisor_node)
builder.add_node("research_agent", research_subgraph)
builder.add_node("summary_agent", summary_subgraph)

builder.add_edge(START, "supervisor")
builder.add_edge("supervisor", "research_agent")
builder.add_edge("research_agent", "summary_agent")
builder.add_edge("summary_agent", END)
graph = builder.compile()


result = graph.invoke(
    {
        "question": "What is LangGraph?",
        "supervisor_prompt": "",
        "research_data": "",
        "final_answer": "",
    }
)

print("\nFinal Output:")
print(result.get("final_answer", "No output"))
