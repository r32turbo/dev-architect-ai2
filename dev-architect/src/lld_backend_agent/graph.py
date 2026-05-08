"""
graph.py
LangGraph pipeline for Backend LLD Agent
"""

import importlib
import logging

from langchain_google_vertexai import ChatVertexAI
from langgraph.graph import StateGraph, START, END

from .configuration import AgentConfig, register_agent_adk
from .prompts import build_backend_lld_prompt, BACKEND_LLD_TASK
from .state import BackendLLDState
from .optimizer import optimize_backend_lld_output, validate_backend_lld_structure, format_backend_lld_for_downstream

logger = logging.getLogger(__name__)


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
        validation_score_threshold=0.75,
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

        attempts = 0
        max_attempts = 3
        output = ""

        while attempts < max_attempts:
            response = react_agent.run(task=task)

            output = (
                response.output
                if isinstance(response.output, str)
                else str(response.output)
            )

            logger.info(f"Attempt {attempts+1}: Raw LLM response chars={len(response.output)}")
            logger.info(f"Attempt {attempts+1}: Initial output chars={len(output)}")

            if len(output) >= 2500:
                break

            attempts += 1
            task += "\n\nCRITICAL: Output is too short. Generate at least 2500 characters with detailed implementation specifics, workflows, and engineering details."

        # Optimize output to fit within 2.5k-10k character range
        output = optimize_backend_lld_output(output, target_min=2500, target_max=10000)
        
        logger.info(f"Optimized output chars={len(output)}")
        
        # Validate structure
        validation = validate_backend_lld_structure(output)
        
        logger.info(f"Validation: valid={validation['valid']}, missing_sections={len(validation['missing_sections'])}, chars={validation['character_count']}")
        
        # Format for downstream consumption
        output = format_backend_lld_for_downstream(output)

        logger.info(f"Final output chars={len(output)}")

        return {"backend_output": output}

    # ---------- Graph ----------
    builder = StateGraph(BackendLLDState)

    builder.add_node("generate_backend_lld", generate_backend_lld)

    builder.add_edge(START, "generate_backend_lld")
    builder.add_edge("generate_backend_lld", END)

    return builder.compile()