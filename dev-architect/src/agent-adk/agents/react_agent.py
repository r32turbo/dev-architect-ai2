"""
ReusableReActAgent – the main public entry point.

Wraps ``langchain.agents.create_agent`` with:

* **Configurable max ReAct iterations** – passed as ``recursion_limit`` in
  the graph invocation config, capping tool-call loops before a forced stop.
* **Structured prompt abstraction** – system and user prompts are built from
  a :class:`~reusableagents.prompts.base.PromptBuilder` and resolved with
  caller-supplied variables at run-time.  The system prompt is forwarded
  directly to ``create_agent`` via its ``system_prompt`` parameter.
* **Output validation + refinement** – an optional
  :class:`~reusableagents.agents.validator.OutputValidator` reviews the
  agent's answer and either accepts it or replaces it with a refined version
  produced by a *different* LLM.
* **Configurable refinement loop** – when the validator does not supply a
  ready-made ``refined_output``, the agent can be re-run with the validator's
  feedback injected as additional context (up to ``max_refinement_attempts``).

Max-iteration semantics
-----------------------
``create_agent`` compiles the graph with ``recursion_limit=10_000`` by
default.  ``ReusableReActAgent`` overrides this at invoke time::

    recursion_limit = max_react_iterations * 2 + 1

Each (model-node + tools-node) pair consumes 2 supersteps; the final
model-node answer consumes 1 more, giving the formula above.
"""

from __future__ import annotations

import logging
from typing import Any, List, Optional, Sequence, Type

from langchain.agents import create_agent
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_core.tools import BaseTool
from pydantic import BaseModel, ConfigDict, Field

from reusableagents.agents.validator import OutputValidator
from reusableagents.config.settings import AgentConfig
from reusableagents.context import AgentContext
from reusableagents.prompts.base import PromptBuilder

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# AgentResponse
# ---------------------------------------------------------------------------


class AgentResponse(BaseModel):
    """
    The fully resolved output of a :class:`ReusableReActAgent` run.

    All fields are validated by Pydantic at construction time.
    ``arbitrary_types_allowed`` is set so that LangChain
    :class:`~langchain_core.messages.BaseMessage` objects can be stored in
    ``raw_messages`` without wrapping.

    Attributes
    ----------
    output:
        Final answer – a plain string when no ``output_schema`` is configured
        on the agent, or a Pydantic model instance conforming to the supplied
        schema after the structured-extraction step.
    is_validated:
        ``True`` when an :class:`~reusableagents.agents.validator.OutputValidator`
        was applied to this response.
    validation_score:
        Quality score returned by the validator (``None`` if not validated).
        When present, must be in ``[0.0, 1.0]``.
    validation_feedback:
        Textual feedback from the validator (``None`` if not validated).
    was_refined:
        ``True`` when the validator replaced the original output with a better
        version.
    refinement_attempts:
        Number of extra agent re-runs triggered because the validator did not
        supply a ready-made ``refined_output``.  Must be ``>= 0``.
    raw_messages:
        The full message history from the LangGraph run (useful for debugging).
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    output: Any = Field(
        description=(
            "Final answer – a plain string when no ``output_schema`` is configured, "
            "or a Pydantic model instance conforming to the schema supplied to "
            "``ReusableReActAgent``."
        ),
    )
    is_validated: bool = Field(
        default=False,
        description="True when an OutputValidator was applied to this response.",
    )
    validation_score: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Quality score in [0, 1] returned by the validator LLM.",
    )
    validation_feedback: Optional[str] = Field(
        default=None,
        description="Textual feedback from the validator LLM.",
    )
    was_refined: bool = Field(
        default=False,
        description="True when the validator replaced the original output.",
    )
    refinement_attempts: int = Field(
        default=0,
        ge=0,
        description="Number of extra agent re-runs triggered for refinement.",
    )
    raw_messages: List[BaseMessage] = Field(
        default_factory=list,
        description="Full message history from the agent run.",
    )


# ---------------------------------------------------------------------------
# ReusableReActAgent
# ---------------------------------------------------------------------------


class ReusableReActAgent:
    """
    A reusable, configurable ReAct agent built on LangGraph.

    Parameters
    ----------
    tools:
        The tools the agent may invoke.  Pass an empty list if the agent
        should operate in a pure LLM (non-tool) mode.
    llm:
        The primary LLM that drives the ReAct loop.
    prompt_builder:
        A :class:`~reusableagents.prompts.base.PromptBuilder` that defines
        the system and user prompt templates.  Variable placeholders
        (``{variable_name}``) are resolved at :meth:`run` time from the
        ``**prompt_variables`` keyword arguments.
    validator:
        An optional :class:`~reusableagents.agents.validator.OutputValidator`
        that reviews the agent's output after the ReAct loop completes.
        When ``None``, or when
        :attr:`~reusableagents.config.settings.AgentConfig.enable_validation`
        is ``False``, validation is skipped entirely.
    config:
        Behavioural settings.  Defaults to
        :class:`~reusableagents.config.settings.AgentConfig` with
        ``max_react_iterations=10``.
    output_schema:
        An optional Pydantic ``BaseModel`` **subclass** (pass the class itself,
        not an instance).  When provided, the agent's final text output is
        post-processed by a dedicated ``with_structured_output`` LLM call that
        maps the text into the schema's fields.  The resulting model instance
        is stored in :attr:`AgentResponse.output` instead of the raw string.
        Validation and refinement, when enabled, still operate on the
        intermediate text before the structured-extraction step.
    context:
        An optional :class:`~reusableagents.context.AgentContext` instance
        carrying session metadata, authentication / authorisation info, and
        shared mutable state.  When ``None``, the agent creates a fresh
        context automatically on the first ``run()`` call.  In a multi-agent
        pipeline the :class:`~reusableagents.agents.supervisor.SupervisorAgent`
        passes the same context to every worker so they can share state.
        A context may also be supplied at ``run()`` time via the special
        ``context`` keyword argument (which takes precedence over the
        constructor-level value).

    Examples
    --------
    ::

        from reusableagents.prompts.base import PromptBuilder
        from reusableagents.llm.gemini import create_agent_llm, create_validator_llm
        from reusableagents.agents.validator import OutputValidator
        from reusableagents.agents.react_agent import ReusableReActAgent
        from reusableagents.config.settings import AgentConfig
        from langchain_core.tools import tool

        @tool
        def add(a: int, b: int) -> int:
            "Add two integers."
            return a + b

        prompt = (
            PromptBuilder()
            .add_system("You are a helpful assistant. Today is {date}.", name="persona")
            .add_user("{question}", name="question")
        )

        agent = ReusableReActAgent(
            tools=[add],
            llm=create_agent_llm(),
            prompt_builder=prompt,
            validator=OutputValidator(create_validator_llm()),
            config=AgentConfig(max_react_iterations=5),
        )

        response = agent.run(date="2026-03-22", question="What is 7 + 8?")
        print(response.output)
    """

    def __init__(
        self,
        tools: Sequence[BaseTool],
        llm: BaseChatModel,
        prompt_builder: PromptBuilder,
        validator: Optional[OutputValidator] = None,
        config: Optional[AgentConfig] = None,
        output_schema: Optional[Type[BaseModel]] = None,
        context: Optional[AgentContext] = None,
    ) -> None:
        # ------------------------------------------------------------------
        # Validate all constructor arguments eagerly so that misconfiguration
        # surfaces at object creation, not buried inside the first .run() call.
        # ------------------------------------------------------------------
        if not isinstance(llm, BaseChatModel):
            raise TypeError(
                f"llm must be a BaseChatModel instance, "
                f"got {type(llm).__name__!r}"
            )
        if not isinstance(prompt_builder, PromptBuilder):
            raise TypeError(
                f"prompt_builder must be a PromptBuilder instance, "
                f"got {type(prompt_builder).__name__!r}"
            )
        if validator is not None and not isinstance(validator, OutputValidator):
            raise TypeError(
                f"validator must be an OutputValidator instance or None, "
                f"got {type(validator).__name__!r}"
            )
        if config is not None and not isinstance(config, AgentConfig):
            raise TypeError(
                f"config must be an AgentConfig instance or None, "
                f"got {type(config).__name__!r}"
            )
        _tools = list(tools)
        _bad_tools = [
            type(t).__name__ for t in _tools if not isinstance(t, BaseTool)
        ]
        if _bad_tools:
            raise TypeError(
                f"All tools must be BaseTool instances; "
                f"got invalid types: {_bad_tools}"
            )
        if output_schema is not None and not (
            isinstance(output_schema, type) and issubclass(output_schema, BaseModel)
        ):
            raise TypeError(
                f"output_schema must be a Pydantic BaseModel subclass "
                f"(pass the class itself, not an instance); "
                f"got {type(output_schema).__name__!r}"
            )
        if context is not None and not isinstance(context, AgentContext):
            raise TypeError(
                f"context must be an AgentContext instance or None, "
                f"got {type(context).__name__!r}"
            )
        # ------------------------------------------------------------------
        self.tools = _tools
        self.llm = llm
        self.prompt_builder = prompt_builder
        self.validator = validator
        self.config = config or AgentConfig()
        self.output_schema: Optional[Type[BaseModel]] = output_schema
        self.context: Optional[AgentContext] = context

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self, **prompt_variables: Any) -> AgentResponse:
        """
        Execute the ReAct agent and return a validated, refined response.

        Parameters
        ----------
        **prompt_variables:
            Keyword arguments substituted into the prompt template.
            Must supply values for every ``{variable}`` used in the
            :class:`~reusableagents.prompts.base.PromptBuilder`.

            A special ``context`` keyword may be passed to supply an
            :class:`~reusableagents.context.AgentContext`.  If neither
            the constructor nor ``run()`` receives a context, one is
            created automatically with default values.

        Returns
        -------
        AgentResponse
            The final (possibly refined) answer together with validation
            metadata and the raw LangGraph message history.

        Raises
        ------
        GraphRecursionError
            If the agent exceeds ``max_react_iterations`` without reaching a
            final answer.  Catch this to handle runaway loops gracefully.
        """
        # --- resolve context (run-time > constructor > auto-create) ---
        ctx = prompt_variables.pop("context", None)
        if ctx is not None and not isinstance(ctx, AgentContext):
            raise TypeError(
                f"context must be an AgentContext instance or None, "
                f"got {type(ctx).__name__!r}"
            )
        if ctx is None:
            ctx = self.context
        if ctx is None:
            ctx = AgentContext()
            logger.debug("Auto-created AgentContext (session=%s)", ctx.session.session_id)
        self.context = ctx

        ctx.record("ReusableReActAgent", "started")

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

        ctx.record(
            "ReusableReActAgent",
            "completed",
            detail=str(response.output)[:200] if response.output else None,
        )

        return response

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _invoke_agent(
        self,
        system_prompt: str,
        user_message: str,
    ) -> tuple[str, List[BaseMessage]]:
        """
        Build a ``langchain.agents.create_agent`` graph and invoke it once.

        The system prompt is passed directly to ``create_agent`` via its
        ``system_prompt`` keyword argument so that it is handled natively
        (prepended before every model call) rather than manually injected
        into the message list.
        """
        # The graph is built fresh each call so the system_prompt can change
        # between invocations (e.g. different variable values).
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
        """Return the text content of the last message in the list."""
        if not messages:
            return ""
        last = messages[-1]
        if isinstance(last.content, str):
            return last.content
        # Handle list-of-dicts content (e.g. tool-call responses).
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
        """
        Re-invoke the agent, appending the validator's feedback as context
        so the agent can self-correct.
        """
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
        """
        Post-process the agent's text output into a structured Pydantic model.

        Uses the agent LLM with ``with_structured_output`` bound to
        :attr:`output_schema` so that the extraction is schema-driven and the
        result is fully validated by Pydantic before being returned.

        Parameters
        ----------
        text_output:
            The raw or refined text produced by the ReAct loop.

        Returns
        -------
        BaseModel
            An instance of :attr:`output_schema` populated from *text_output*.
        """
        assert self.output_schema is not None  # guarded by caller
        structured_llm = self.llm.with_structured_output(self.output_schema)
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
        """
        Validate the agent output and refine it if the validator rejects it.

        Refinement strategy
        -------------------
        1. If the validator's ``ValidationResult.refined_output`` is non-null,
           use it directly (zero additional agent calls).
        2. Otherwise re-run the agent up to ``max_refinement_attempts`` times,
           injecting the validator's feedback as additional context.
        3. Accept the best response obtained even if refinement attempts are
           exhausted.
        """
        assert self.validator is not None  # guarded by caller

        validation = self.validator.validate(
            original_input=original_input,
            agent_output=agent_output,
        )
        logger.info(
            "Validation result – is_valid=%s, score=%.2f",
            validation.is_valid,
            validation.score,
        )
        logger.debug("Validation feedback: %s", validation.feedback)

        if validation.is_valid:
            output_size = len(str(agent_output))
            token_estimate = max(1, output_size // 4)
            logger.info(
                "Agent output profiling: size=%d chars, tokens_est=%d, validation_score=%.2f, was_refined=%s",
                output_size,
                token_estimate,
                validation.score,
                False,
            )
            return AgentResponse(
                output=agent_output,
                is_validated=True,
                validation_score=validation.score,
                validation_feedback=validation.feedback,
                was_refined=False,
                refinement_attempts=0,
                raw_messages=raw_messages,
            )

        # --- Not valid: try to improve ---

        # Strategy 1: validator already produced a refined version.
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

        # Strategy 2: re-run the agent with feedback.
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

            # Re-validate the new output.
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

            # If the validator now provides a refined version, prefer it.
            if validation.refined_output:
                logger.info("Using validator-supplied refined output after re-run.")
                current_output = validation.refined_output
                break

        output_size = len(str(current_output))
        token_estimate = max(1, output_size // 4)
        input_size = len(str(agent_output))
        compression_ratio = float(input_size) / max(1, output_size)
        logger.info(
            "Agent output profiling: size=%d chars, tokens_est=%d, validation_score=%.2f, was_refined=%s, attempts=%d, compression_ratio=%.2f",
            output_size,
            token_estimate,
            validation.score,
            True,
            attempts,
            compression_ratio,
        )
        return AgentResponse(
            output=current_output,
            is_validated=True,
            validation_score=validation.score,
            validation_feedback=validation.feedback,
            was_refined=True,
            refinement_attempts=attempts,
            raw_messages=current_messages,
        )
