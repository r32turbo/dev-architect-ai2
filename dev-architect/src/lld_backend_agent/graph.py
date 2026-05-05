"""
graph.py
LangGraph pipeline for Backend LLD Agent
"""

import importlib

from langchain_google_vertexai import ChatVertexAI
from langgraph.graph import StateGraph, START, END

from configuration import AgentConfig, register_agent_adk
from prompts import build_backend_lld_prompt, BACKEND_LLD_TASK
from state import BackendLLDState


# Register ADK
register_agent_adk()

ReusableReActAgent = importlib.import_module(
    "reusableagents.agents.react_agent"
).ReusableReActAgent

OutputValidator = importlib.import_module(
    "reusableagents.agents.validator"
).OutputValidator


def build_graph():
    # ---------- LLM ----------
    llm = ChatVertexAI(
        model_name="gemini-2.5-flash-lite",
        project="eds-alchemy",
        location="us-central1",
        temperature=0.0,
    )

    # ---------- Config ----------
    agent_config = AgentConfig(
        max_react_iterations=5,
        enable_validation=True,
        validation_score_threshold=0.7,
        max_refinement_attempts=2,
    )

    validator = OutputValidator(
        llm=llm,
        score_threshold=agent_config.validation_score_threshold,
    )

    # ---------- Agent ----------
    # ---------- Node ----------
    def generate_backend_lld(state: BackendLLDState):
        lld_input = state["lld_input"]
        # Escape literal braces in the input to avoid formatting errors
        escaped_input = lld_input.replace("{", "{{").replace("}", "}}")
        task = BACKEND_LLD_TASK.format(lld_input=escaped_input)

        react_agent = ReusableReActAgent(
            tools=[],
            llm=llm,
            prompt_builder=build_backend_lld_prompt(lld_input),
            validator=validator,
            config=agent_config,
        )

        response = react_agent.run(task=task)

        output = (
            response.output
            if isinstance(response.output, str)
            else str(response.output)
        )

        return {"backend_output": output}

    # ---------- Graph ----------
    builder = StateGraph(BackendLLDState)

    builder.add_node("generate_backend_lld", generate_backend_lld)

    builder.add_edge(START, "generate_backend_lld")
    builder.add_edge("generate_backend_lld", END)

    return builder.compile()