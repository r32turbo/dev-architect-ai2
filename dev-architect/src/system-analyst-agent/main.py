import os
import sys
import importlib
import warnings
from pathlib import Path
from typing import TypedDict

from dotenv import load_dotenv
from langgraph.graph import StateGraph, START, END
from langchain_google_vertexai import ChatVertexAI

from prompt import SYSTEM_ANALYST_PROMPT

# Hide known ChatVertexAI deprecation warnings from terminal output.
warnings.filterwarnings(
    "ignore",
    message=r".*ChatVertexAI.*deprecated.*",
    category=Warning,
)
warnings.filterwarnings(
    "ignore",
    message=r".*Use \[`ChatGoogleGenerativeAI`\].*",
    category=Warning,
)

ADK_ROOT = Path(__file__).resolve().parents[1] / "agent-adk"
if str(ADK_ROOT) not in sys.path:
    sys.path.insert(0, str(ADK_ROOT))


def load_adk_components():
    react_mod = importlib.import_module("agents.react_agent")
    prompts_mod = importlib.import_module("prompts.base")
    config_mod = importlib.import_module("config.settings")
    validator_mod = importlib.import_module("agents.validator")
    return (
        react_mod.ReusableReActAgent,
        prompts_mod.PromptBuilder,
        config_mod.AgentConfig,
        validator_mod.OutputValidator,
    )


REQUIRED_SECTIONS = [
    "introduction",
    "project goal",
    "scope",
    "functional requirements",
    "non functional requirements",
    "assumptions",
    "out of scope",
    "acceptance criteria",
    "risks and mitigations",
]


def normalize_text(text: str) -> str:
    return "".join(ch if ch.isalnum() or ch.isspace() else " " for ch in text.lower())


# ---------------- ENV ----------------
def load_environment():
    for path in [Path.cwd(), *Path.cwd().parents]:
        env_file = path / ".env"
        if env_file.exists():
            load_dotenv(env_file)
            break


# ---------------- LLM ----------------
def create_llm(model: str):
    return ChatVertexAI(
        model_name=model,
        project=os.getenv("GOOGLE_CLOUD_PROJECT", "eds-alchemy"),
        location=os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1"),
        temperature=0.0,
        max_output_tokens=8192,
    )


# ---------------- AGENT SETUP ----------------
def build_agent():
    ReusableReActAgent, PromptBuilder, AgentConfig, OutputValidator = load_adk_components()

    llm = create_llm(os.getenv("GEMINI_AGENT_MODEL", "gemini-2.5-flash-lite"))
    validator_llm = create_llm(os.getenv("GEMINI_VALIDATOR_MODEL", "gemini-2.5-flash-lite"))

    validator = OutputValidator(llm=validator_llm)

    prompt_builder = (
        PromptBuilder()
        .add_system(SYSTEM_ANALYST_PROMPT)
        .add_user("{user_goal}")
    )

    return ReusableReActAgent(
        tools=[],
        llm=llm,
        prompt_builder=prompt_builder,
        validator=validator,
        config=AgentConfig(
            max_react_iterations=5,
            enable_validation=True,
            max_refinement_attempts=2,
        ),
    )


# ---------------- STATE ----------------
class AgentState(TypedDict):
    user_goal: str
    output: str


# ---------------- NODE ----------------
def analyst_node(state: AgentState):
    result = agent.run(user_goal=state["user_goal"])
    return {"output": result.output}


# ---------------- GRAPH ----------------
def build_graph():
    graph = StateGraph(AgentState)
    graph.add_node("analyst", analyst_node)
    graph.add_edge(START, "analyst")
    graph.add_edge("analyst", END)
    return graph.compile()


# ---------------- MAIN ----------------
def main():
    load_environment()

    global agent
    agent = build_agent()

    app = build_graph()

    user_goal = "Create a one page marketing website using NextJS ."

    result = app.invoke({"user_goal": user_goal})
    output = result.get("output", "").strip()

    # Keep structure simple, with at most one follow-up pass if output looks incomplete.
    if output:
        normalized_output = normalize_text(output)
        missing_sections = [s for s in REQUIRED_SECTIONS if s not in normalized_output]

        last_line = output.splitlines()[-1].strip() if output.splitlines() else ""
        looks_truncated = output.endswith((":", "|", "-", "*", "```")) or last_line.startswith("|")

        if missing_sections or looks_truncated:
            continuation_prompt = (
                "Provide ONLY the missing sections listed below. "
                "Do not repeat sections already present. "
                "Use markdown headings and bullet points only. Do not use tables.\n\n"
                f"Missing sections: {', '.join(missing_sections) if missing_sections else 'none'}\n\n"
                "If no sections are missing, return an empty response."
            )

            follow_up = agent.run(user_goal=continuation_prompt).output
            follow_up_text = follow_up.strip() if isinstance(follow_up, str) else str(follow_up).strip()

            if follow_up_text and follow_up_text != output:
                if output in follow_up_text and len(follow_up_text) > len(output):
                    output = follow_up_text
                elif follow_up_text not in output and "no sections are missing" not in follow_up_text.lower():
                    output = f"{output}\n\n{follow_up_text}"

    if output:
        print(output)
    else:
        print("No output generated.")


if __name__ == "__main__":
    main()