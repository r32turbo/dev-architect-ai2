"""
generic_graph.py
Builds and returns the ReusableReActAgent for the Generic LLD Agent.
Includes MLflow observability — structured logging + native MLflow tracing.
"""
import importlib
import importlib.util
import sys
from pathlib import Path

# ── Add agent dir to path ─────────────────────────────────────────────────────
_AGENT_DIR = str(Path(__file__).resolve().parent)
if _AGENT_DIR not in sys.path:
    sys.path.insert(0, _AGENT_DIR)

_SRC_DIR = str(Path(__file__).resolve().parents[1])
if _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)

# ── Observability ─────────────────────────────────────────────────────────────
from observability.observability import get_logger, trace_agent

logger = get_logger(__name__)


def _import_from_agent(module_name: str):
    spec = importlib.util.spec_from_file_location(
        f"generic_lld_agent.{module_name}",
        Path(__file__).resolve().parent / f"{module_name}.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ── Load agent modules ────────────────────────────────────────────────────────
_configuration       = _import_from_agent("generic_configuration")
_prompts             = _import_from_agent("generic_prompts")

register_agent_adk   = _configuration.register_agent_adk
GeminiConfig         = _configuration.GeminiConfig
AgentConfig          = _configuration.AgentConfig
create_agent_llm     = _configuration.create_agent_llm
create_validator_llm = _configuration.create_validator_llm
GENERIC_LLD_PROMPT   = _prompts.GENERIC_LLD_PROMPT

register_agent_adk()

ReusableReActAgent = importlib.import_module("reusableagents.agents.react_agent").ReusableReActAgent
OutputValidator    = importlib.import_module("reusableagents.agents.validator").OutputValidator
AgentContext       = importlib.import_module("reusableagents.context").AgentContext
SessionInfo        = importlib.import_module("reusableagents.context").SessionInfo
AuthInfo           = importlib.import_module("reusableagents.context").AuthInfo


def build_agent():
    """Build and return the Generic LLD ReAct agent."""
    logger.info("Building Generic LLD Agent ...")

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

    agent_config = AgentConfig(
        max_react_iterations=5,
        enable_validation=True,
        validation_score_threshold=0.7,
        max_refinement_attempts=2,
    )

    validator = OutputValidator(
        llm=validator_llm,
        score_threshold=agent_config.validation_score_threshold,
    )

    agent = ReusableReActAgent(
        tools=[],
        llm=agent_llm,
        prompt_builder=GENERIC_LLD_PROMPT,
        validator=validator,
        config=agent_config,
    )

    logger.info("Generic LLD Agent built successfully.")
    return agent


@trace_agent("generic_lld")
def run_agent(agent, context, user_input, requirement_doc, architecture_doc):
    """Run the Generic LLD agent with MLflow tracing."""
    logger.info("Running Generic LLD Agent. session_id=%s", context.session.session_id)
    response = agent.run(
        context=context,
        user_input=user_input,
        requirement_doc=requirement_doc,
        architecture_doc=architecture_doc,
    )
    logger.info(
        "Generic LLD completed. score=%.2f refined=%s",
        response.validation_score or 0,
        response.was_refined,
    )
    return response


def create_context(user_id: str = "api-user", session_metadata: dict = None) -> AgentContext:
    """Create an AgentContext for the Generic LLD Agent."""
    return AgentContext(
        session=SessionInfo(
            metadata=session_metadata or {"source": "generic-lld-agent"},
        ),
        auth=AuthInfo(
            user_id=user_id,
            roles=["lld-generator"],
            permissions=["generate", "read"],
        ),
        state={},
    )