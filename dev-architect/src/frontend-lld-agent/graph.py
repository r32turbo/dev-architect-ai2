"""
graph.py
Builds and returns the ReusableReActAgent for the Frontend LLD Agent.
Uses AgentContext from the updated agent-adk.
"""
import logging
import importlib
import importlib.util
import sys
from pathlib import Path

# Import this agent's own modules strictly by file path
_AGENT_DIR = str(Path(__file__).resolve().parent)
if _AGENT_DIR not in sys.path:
    sys.path.insert(0, _AGENT_DIR)


def _import_from_agent(module_name: str):
    """Import a module strictly from this agent's own directory."""
    spec = importlib.util.spec_from_file_location(
        f"frontend_lld_agent.{module_name}",
        Path(__file__).resolve().parent / f"{module_name}.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_configuration       = _import_from_agent("configuration")
_prompts             = _import_from_agent("prompts")

register_agent_adk   = _configuration.register_agent_adk
GeminiConfig         = _configuration.GeminiConfig
AgentConfig          = _configuration.AgentConfig
create_agent_llm     = _configuration.create_agent_llm
create_validator_llm = _configuration.create_validator_llm
FRONTEND_LLD_PROMPT  = _prompts.FRONTEND_LLD_PROMPT

register_agent_adk()

logger = logging.getLogger(__name__)

ReusableReActAgent = importlib.import_module("reusableagents.agents.react_agent").ReusableReActAgent
OutputValidator    = importlib.import_module("reusableagents.agents.validator").OutputValidator
AgentContext       = importlib.import_module("reusableagents.context").AgentContext
SessionInfo        = importlib.import_module("reusableagents.context").SessionInfo
AuthInfo           = importlib.import_module("reusableagents.context").AuthInfo


def build_agent() -> ReusableReActAgent:
    """
    Build and return the Frontend LLD ReAct agent.
    Called by the supervisor or main.py with:
        agent.run(
            context=ctx,
            user_input=...,
            requirement_doc=...,
            architecture_doc=...,
        )
    """
    logger.info("Building Frontend LLD Agent ...")

    # Step 1 – LLM config using GeminiConfig
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
    logger.info("LLMs created using GeminiConfig.")

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

    logger.info("Frontend LLD Agent built successfully.")
    return agent


def create_context(user_id: str = "api-user", session_metadata: dict = None) -> AgentContext:
    """
    Create an AgentContext for the Frontend LLD Agent.
    Called by main.py / FastAPI to create a context per request.
    """
    return AgentContext(
        session=SessionInfo(
            metadata=session_metadata or {"source": "frontend-lld-agent"},
        ),
        auth=AuthInfo(
            user_id=user_id,
            roles=["lld-generator"],
            permissions=["generate", "read"],
        ),
        state={},
    )