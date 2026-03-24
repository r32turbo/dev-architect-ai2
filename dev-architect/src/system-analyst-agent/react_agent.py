"""ReusableReActAgent – the main public entry point."""

from typing import Any, List, Optional, Sequence, Type
import logging

from langchain.agents import create_agent
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage, HumanMessage
from langchain_core.tools import BaseTool
from pydantic import BaseModel, ConfigDict, Field

from config import AgentConfig
from prompts_builder import PromptBuilder
from validator import OutputValidator

logger = logging.getLogger(__name__)


class AgentResponse(BaseModel):
    """
    The fully resolved output of a ReusableReActAgent run.

    Attributes
    ----------
    output:
        Final answer – plain string by default.
    is_validated:
        True when an OutputValidator was applied.
    validation_score:
        Quality score from validator (0.0 to 1.0), or None if not validated.
    validation_feedback:
        Textual feedback from the validator, or None if not validated.
    was_refined:
        True when the validator replaced the original output.
    refinement_attempts:
        Number of extra agent re-runs for refinement.
    raw_messages:
        Full message history from the LangGraph run (for debugging).
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    output: Any = Field(description="Final answer from the agent.")
    is_validated: bool = Field(default=False, description="True if OutputValidator was applied.")
    validation_score: Optional[float] = Field(
        default=None, ge=0.0, le=1.0, description="Validation score in [0, 1]."
    )
    validation_feedback: Optional[str] = Field(
        default=None, description="Feedback from the validator."
    )
    was_refined: bool = Field(
        default=False, description="True if validator replaced the output."
    )
    refinement_attempts: int = Field(
        default=0, ge=0, description="Number of refinement iteration re-runs."
    )
    raw_messages: List[BaseMessage] = Field(
        default_factory=list, description="Full message history from agent run."
    )


class ReusableReActAgent:
    """
    A reusable, configurable ReAct agent built on LangGraph.

    Parameters
    ----------
    tools:
        The tools the agent may invoke.  Pass an empty list for pure LLM mode.
    llm:
        The primary LLM that drives the ReAct loop.
    prompt_builder:
        A PromptBuilder that defines system and user prompt templates.
        Variable placeholders like {variable_name} are resolved at run-time.
    validator:
        Optional OutputValidator that reviews the agent's output.
    config:
        AgentConfig with behavioral settings (max_react_iterations, etc).
        Defaults to AgentConfig() with max_react_iterations=10.
    output_schema:
        Optional Pydantic BaseModel subclass for structured output extraction.
    """

    def __init__(
        self,
        tools: Sequence[BaseTool],
        llm: BaseChatModel,
        prompt_builder: PromptBuilder,
        validator: Optional[OutputValidator] = None,
        config: Optional[AgentConfig] = None,
        output_schema: Optional[Type[BaseModel]] = None,
    ) -> None:
        """Initialize ReusableReActAgent with validation."""
        if not isinstance(llm, BaseChatModel):
            raise TypeError(
                f"llm must be a BaseChatModel instance, got {type(llm).__name__!r}"
            )
        if not isinstance(prompt_builder, PromptBuilder):
            raise TypeError(
                f"prompt_builder must be a PromptBuilder instance, got {type(prompt_builder).__name__!r}"
            )
        if validator is not None and not isinstance(validator, OutputValidator):
            raise TypeError(
                f"validator must be an OutputValidator instance or None, got {type(validator).__name__!r}"
            )
        if config is not None and not isinstance(config, AgentConfig):
            raise TypeError(
                f"config must be an AgentConfig instance or None, got {type(config).__name__!r}"
            )

        _tools = list(tools)
        _bad_tools = [type(t).__name__ for t in _tools if not isinstance(t, BaseTool)]
        if _bad_tools:
            raise TypeError(
                f"All tools must be BaseTool instances; got invalid types: {_bad_tools}"
            )

        if output_schema is not None and not (
            isinstance(output_schema, type) and issubclass(output_schema, BaseModel)
        ):
            raise TypeError(
                f"output_schema must be a Pydantic BaseModel subclass, got {type(output_schema).__name__!r}"
            )

        self.tools = _tools
        self.llm = llm
        self.prompt_builder = prompt_builder
        self.validator = validator
        self.config = config or AgentConfig()
        self.output_schema = output_schema

    def run(self, **prompt_variables: Any) -> AgentResponse:
        """
        Execute the ReAct agent and return a validated, refined response.

        Parameters
        ----------
        **prompt_variables:
            Keyword arguments substituted into the prompt templates.

        Returns
        -------
        AgentResponse
            Final answer with validation metadata and message history.
        """
        system_prompt = self.prompt_builder.render_system(**prompt_variables)
        user_message = self.prompt_builder.render_user(**prompt_variables)

        output, messages = self._invoke_agent(system_prompt, user_message)

        if self.validator and self.config.enable_validation:
            response = self._validate_and_refine(
                system_prompt=system_prompt,
                original_input=user_message,
                agent_output=output,
                raw_messages=messages,
                prompt_variables=prompt_variables,
            )
        else:
            response = AgentResponse(output=output, raw_messages=messages)

        if self.output_schema is not None:
            text = response.output if isinstance(response.output, str) else str(response.output)
            structured = self._extract_structured_output(text)
            response = response.model_copy(update={"output": structured})

        return response

    def _invoke_agent(
        self,
        system_prompt: str,
        user_message: str,
    ) -> tuple[str, List[BaseMessage]]:
        """Build and invoke the LangGraph agent."""
        graph = create_agent(
            model=self.llm,
            tools=self.tools,
            system_prompt=system_prompt if system_prompt.strip() else None,
        )

        recursion_limit = self.config.max_react_iterations * 2 + 1
        logger.debug(
            "Invoking ReAct agent (max_iterations=%d, recursion_limit=%d)",
            self.config.max_react_iterations,
            recursion_limit,
        )

        result = graph.invoke(
            {"messages": [HumanMessage(content=user_message)]},
            config={"recursion_limit": recursion_limit},
        )

        messages: List[BaseMessage] = result.get("messages", [])
        output = self._extract_text(messages)
        return output, messages

    @staticmethod
    def _extract_text(messages: List[BaseMessage]) -> str:
        """Extract text content from the last message."""
        if not messages:
            return ""
        last = messages[-1]
        if isinstance(last.content, str):
            return last.content
        if isinstance(last.content, list):
            parts = [
                c.get("text", "") if isinstance(c, dict) else str(c)
                for c in last.content
            ]
            return "".join(parts)
        return str(last.content)

    def _invoke_agent_with_feedback(
        self,
        system_prompt: str,
        original_input: str,
        previous_output: str,
        feedback: str,
    ) -> tuple[str, List[BaseMessage]]:
        """Re-invoke agent with validator feedback for refinement."""
        refinement_user_message = (
            f"{original_input}\n\n"
            "---\n"
            "**Previous attempt (needs improvement)**\n\n"
            f"{previous_output}\n\n"
            "---\n"
            "**Improvement feedback**\n\n"
            f"{feedback}\n\n"
            "Please provide an improved response that addresses the feedback above."
        )
        return self._invoke_agent(system_prompt, refinement_user_message)

    def _extract_structured_output(self, text_output: str) -> BaseModel:
        """Post-process text output into a structured Pydantic model."""
        assert self.output_schema is not None
        structured_llm = self.llm.with_structured_output(self.output_schema)
        from langchain_core.messages import SystemMessage

        messages = [
            SystemMessage(
                content=(
                    "You are a precise data-extraction assistant. "
                    "Given the text below, populate the required structured output "
                    "fields exactly as described. "
                    "Do not invent or omit any information present in the text."
                )
            ),
            HumanMessage(content=text_output),
        ]
        logger.debug(
            "Extracting structured output using schema %r …",
            self.output_schema.__name__,
        )
        return structured_llm.invoke(messages)

    def _validate_and_refine(
        self,
        system_prompt: str,
        original_input: str,
        agent_output: str,
        raw_messages: List[BaseMessage],
        prompt_variables: dict[str, Any],
    ) -> AgentResponse:
        """Validate output and refine if needed."""
        assert self.validator is not None

        validation = self.validator.validate(
            original_input=original_input,
            agent_output=agent_output,
        )
        logger.info(
            "Validation result – is_valid=%s, score=%.2f",
            validation.is_valid,
            validation.score,
        )

        if validation.is_valid:
            return AgentResponse(
                output=agent_output,
                is_validated=True,
                validation_score=validation.score,
                validation_feedback=validation.feedback,
                was_refined=False,
                refinement_attempts=0,
                raw_messages=raw_messages,
            )

        # Not valid: try to improve
        if validation.refined_output:
            logger.info("Using validator-supplied refined output.")
            return AgentResponse(
                output=validation.refined_output,
                is_validated=True,
                validation_score=validation.score,
                validation_feedback=validation.feedback,
                was_refined=True,
                refinement_attempts=0,
                raw_messages=raw_messages,
            )

        # Re-run agent with feedback
        current_output = agent_output
        current_messages = raw_messages
        attempts = 0

        for attempt in range(1, self.config.max_refinement_attempts + 1):
            logger.info(
                "Re-running agent with validator feedback (attempt %d/%d) …",
                attempt,
                self.config.max_refinement_attempts,
            )
            current_output, current_messages = self._invoke_agent_with_feedback(
                system_prompt=system_prompt,
                original_input=original_input,
                previous_output=current_output,
                feedback=validation.feedback,
            )
            attempts = attempt

            validation = self.validator.validate(
                original_input=original_input,
                agent_output=current_output,
            )
            logger.info(
                "Re-validation result – is_valid=%s, score=%.2f",
                validation.is_valid,
                validation.score,
            )

            if validation.is_valid:
                break

            if validation.refined_output:
                logger.info("Using validator-supplied refined output after re-run.")
                current_output = validation.refined_output
                break

        return AgentResponse(
            output=current_output,
            is_validated=True,
            validation_score=validation.score,
            validation_feedback=validation.feedback,
            was_refined=True,
            refinement_attempts=attempts,
            raw_messages=current_messages,
        )
