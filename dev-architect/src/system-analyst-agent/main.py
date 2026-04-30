import os
from pathlib import Path
from typing import TypedDict

from dotenv import load_dotenv
from langgraph.graph import END, START, StateGraph
from langchain_google_vertexai import ChatVertexAI

from prompt import SYSTEM_ANALYST_PROMPT
import os
from react_agent import ReusableReActAgent
from prompts_builder import PromptBuilder
from config import AgentConfig


# ---------------- ENV ----------------
current_dir = Path(__file__).resolve().parent
for candidate in [current_dir, *current_dir.parents]:
    env_path = candidate / ".env"
    if env_path.exists():
        load_dotenv(dotenv_path=env_path, override=False)


# ---------------- LLM ----------------
llm = ChatVertexAI(
    model_name="gemini-2.5-flash-lite",
    project="eds-alchemy",
    location="us-central1",
)


# ---------------- PROMPT BUILDER ----------------
# Allow optional supporting documents from environment for standalone runs
requirement_doc = os.getenv("SYSTEM_ANALYST_REQUIREMENT_DOC", "")
architecture_doc = os.getenv("SYSTEM_ANALYST_ARCHITECTURE_DOC", "")
system_prompt = SYSTEM_ANALYST_PROMPT.format(
    requirement_doc=requirement_doc,
    architecture_doc=architecture_doc,
)

prompt_builder = (
    PromptBuilder()
    .add_system(system_prompt, name="system")
    .add_user("{user_goal}", name="user")
)


# ---------------- REACT AGENT ----------------
analyst_agent = ReusableReActAgent(
    tools=[],
    llm=llm,
    prompt_builder=prompt_builder,
    config=AgentConfig(max_react_iterations=5),
)


# ---------------- STATE ----------------
class AgentState(TypedDict):
    user_goal: str
    analyst_output: str


# ---------------- NODE ----------------
def system_analyst_node(state: AgentState):
    response = analyst_agent.run(user_goal=state["user_goal"])

    return {
        "analyst_output": response.output
    }


# ---------------- GRAPH ----------------
builder = StateGraph(AgentState)
builder.add_node("system_analyst", system_analyst_node)
builder.add_edge(START, "system_analyst")
builder.add_edge("system_analyst", END)

graph = builder.compile()


# ---------------- MAIN ----------------
def main() -> None:
    result = graph.invoke(
        {
            "user_goal": "Create a one page marketing website using NextJS with hero, about, services and location sections."
        }
    )

    print(result["analyst_output"])


if __name__ == "__main__":
    main()