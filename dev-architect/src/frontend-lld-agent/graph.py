import importlib

from configuration import (
    GeminiConfig,
    AgentConfig,
    create_agent_llm,
    create_validator_llm,
    register_agent_adk,
)
from prompts import FRONTEND_LLD_PROMPT

register_agent_adk()

ReusableReActAgent = importlib.import_module("reusableagents.agents.react_agent").ReusableReActAgent
OutputValidator    = importlib.import_module("reusableagents.agents.validator").OutputValidator


def build_agent() -> ReusableReActAgent:
    """
    Build and return the Frontend LLD ReAct agent.
    Called by the supervisor with:
        agent.run(
            user_input=...,
            requirement_doc=...,
            architecture_doc=...,
        )
    """
    # Step 1 – LLM config using GeminiConfig (same as sample main.py)
    gemini_config = GeminiConfig(
        project_id="eds-alchemy",
        location="us-central1",
        agent_model="gemini-2.5-flash-lite",
        validator_model="gemini-2.5-flash-lite",
        agent_temperature=0.0,
        validator_temperature=0.0,
    )

    agent_llm     = create_agent_llm(gemini_config)
    validator_llm = create_validator_llm(gemini_config)

    # Step 2 – Behavioural config
    agent_config = AgentConfig(
        max_react_iterations=5,
        enable_validation=True,
        validation_score_threshold=0.7,
        max_refinement_attempts=2,
    )

    # Step 3 – Validator
    validator = OutputValidator(
        llm=validator_llm,
        score_threshold=agent_config.validation_score_threshold,
    )

    # Step 4 – Assemble agent
    agent = ReusableReActAgent(
        tools=[],
        llm=agent_llm,
        prompt_builder=FRONTEND_LLD_PROMPT,
        validator=validator,
        config=agent_config,
    )

    return agent