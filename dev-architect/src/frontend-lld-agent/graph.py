import importlib

from langchain_google_vertexai import ChatVertexAI
from langgraph.graph import END, START, StateGraph

from configuration import AgentConfig, register_agent_adk
from prompts import LLD_PROMPT, LLD_TASK
from state import FrontendLLDState, ARCHITECTURE_DOC

register_agent_adk()

ReusableReActAgent = importlib.import_module("reusableagents.agents.react_agent").ReusableReActAgent
OutputValidator    = importlib.import_module("reusableagents.agents.validator").OutputValidator


def build_graph():
    llm = ChatVertexAI(
        model_name="gemini-2.5-flash-lite",
        project="eds-alchemy",
        location="us-central1",
        temperature=0.0,
    )

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

    react_agent = ReusableReActAgent(
        tools=[],
        llm=llm,
        prompt_builder=LLD_PROMPT,
        validator=validator,
        config=agent_config,
    )

    def generate_lld(state: FrontendLLDState) -> dict:
        task = LLD_TASK.format(architecture_doc=state["architecture_doc"])
        response = react_agent.run(task=task)
        output = response.output if isinstance(response.output, str) else str(response.output)
        return {"final_lld": output}

    builder = StateGraph(FrontendLLDState)
    builder.add_node("generate_lld", generate_lld)
    builder.add_edge(START, "generate_lld")
    builder.add_edge("generate_lld", END)

    return builder.compile()