import os
from pathlib import Path
from typing import TypedDict
from langgraph.graph import StateGraph, START, END
from langchain_core.messages import HumanMessage
from langchain_groq import ChatGroq


env_path = Path(__file__).resolve().parent / ".env"
if env_path.exists() and "GROQ_API_KEY" not in os.environ:
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if line.startswith("GROQ_API_KEY="):
            os.environ["GROQ_API_KEY"] = line.split("=", 1)[1].strip().strip('"').strip("'")
            break

groq_api_key = os.getenv("GROQ_API_KEY")
if not groq_api_key:
    raise RuntimeError(
        "Missing GROQ_API_KEY. Set it in your environment or in Alchemy/.env, "
        "then rerun the script."
    )

groq_model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")


# LLM
llm = ChatGroq(
    model=groq_model,
    temperature=0,
    api_key=groq_api_key,
)


# Graph State
class AgentState(TypedDict):
    user_goal: str
    analyst_output: str


SYSTEM_ANALYST_PROMPT = """
You are a professional System Analyst.

Convert the user goal into a structured System Analyst document.

User Goal:
{user_goal}
"""


# Node
def system_analyst_node(state: AgentState):

    prompt = SYSTEM_ANALYST_PROMPT.format(
        user_goal=state["user_goal"]
    )

    response = llm.invoke([HumanMessage(content=prompt)])

    return {
        "analyst_output": response.content
    }


# Graph
builder = StateGraph(AgentState)

builder.add_node("system_analyst", system_analyst_node)

builder.add_edge(START, "system_analyst")
builder.add_edge("system_analyst", END)

graph = builder.compile()


# Run
result = graph.invoke({
    "user_goal": "Create a one page marketing website using NextJS with hero, about, services and location sections."
})

print(result["analyst_output"])