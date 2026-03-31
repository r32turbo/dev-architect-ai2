"""
Output validation and refinement module.

``OutputValidator`` wraps a *separate* LLM and evaluates the quality of
an agent's response.  When the response is below an acceptable threshold,
the validator LLM is also asked to produce a refined version directly,
avoiding the need for a costly full agent re-run in many cases.

Validation result schema
------------------------
The validator uses ``with_structured_output`` to extract a
:class:`ValidationResult` Pydantic model from the LLM's response, giving
a machine-readable quality score, textual feedback, and an optional
drop-in replacement output.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from langchain_core.language_models import BaseChatModel
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from reusableagents.prompts.base import PromptBuilder

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Default validation prompt
# ---------------------------------------------------------------------------

_DEFAULT_VALIDATION_SYSTEM = """\
You are an expert output quality assessor and editor.

Your task is to critically evaluate an AI-generated response against the \
original request, then return a structured assessment.

Evaluation dimensions
---------------------
1. **Accuracy**      – Is the information factually correct?
2. **Completeness**  – Does the response fully address every part of the request?
3. **Clarity**       – Is the response clear, well-organised, and easy to follow?
4. **Relevance**     – Is every part of the response relevant to the request?

Scoring
-------
Assign a *score* between 0.0 (completely unacceptable) and 1.0 (perfect).

Refinement
----------
When the score is below the acceptable threshold, write an improved version \
of the response in the ``refined_output`` field.  The refined version must \
directly answer the original request without any meta-commentary.\
"""

_DEFAULT_VALIDATION_USER = """\
## Original Request

{original_input}

## Agent Response to Evaluate

{agent_output}

Provide your structured assessment now.\
"""


def _build_default_validation_prompt() -> PromptBuilder:
    return (
        PromptBuilder()
        .add_system(_DEFAULT_VALIDATION_SYSTEM, name="validation_system")
        .add_user(_DEFAULT_VALIDATION_USER, name="validation_user")
    )


# ---------------------------------------------------------------------------
# Pydantic result schema
# ---------------------------------------------------------------------------


class ValidationResult(BaseModel):
    """
    Structured output produced by the validator LLM.

    Attributes
    ----------
    is_valid:
        ``True`` when the agent response meets quality criteria.
    score:
        Continuous quality score in ``[0, 1]``.
    feedback:
        Human-readable explanation of the assessment, including specific
        issues found and suggestions for improvement.
    refined_output:
        An improved version of the response when ``is_valid`` is ``False``.
        ``None`` when the original response is acceptable.
    """

    is_valid: bool = Field(
        description="True if the response meets quality criteria, False otherwise."
    )
    score: float = Field(
        ge=0.0,
        le=1.0,
        description="Quality score from 0.0 (unacceptable) to 1.0 (perfect).",
    )
    feedback: str = Field(
        description=(
            "Detailed feedback on accuracy, completeness, clarity, and relevance. "
            "Include specific issues and improvement suggestions."
        )
    )
    refined_output: Optional[str] = Field(
        default=None,
        description=(
            "A fully corrected, improved version of the response. "
            "Provide this whenever is_valid is False. "
            "Omit (null) when the original response is already acceptable."
        ),
    )

    @field_validator("feedback")
    @classmethod
    def _feedback_not_empty(cls, v: str) -> str:
        """Ensure the validator always returns substantive feedback."""
        if not v.strip():
            raise ValueError("feedback must not be an empty string")
        return v.strip()

    @model_validator(mode="after")
    def _score_consistent_with_is_valid(self) -> "ValidationResult":
        """
        Cross-field consistency check.

        A score of ``0.0`` paired with ``is_valid=True``, or a score of
        ``1.0`` paired with ``is_valid=False``, indicates an internally
        inconsistent LLM response.  Both cases raise ``ValueError`` so that
        downstream code never acts on a contradictory result.
        """
        if self.is_valid and self.score == 0.0:
            raise ValueError(
                "Inconsistent ValidationResult: is_valid=True but score=0.0"
            )
        if not self.is_valid and self.score == 1.0:
            raise ValueError(
                "Inconsistent ValidationResult: is_valid=False but score=1.0"
            )
        return self


# ---------------------------------------------------------------------------
# OutputValidatorConfig
# ---------------------------------------------------------------------------


class OutputValidatorConfig(BaseModel):
    """
    Validated constructor configuration for :class:`OutputValidator`.

    Separating construction-time parameters into their own Pydantic model
    means that an invalid ``score_threshold`` is caught immediately at
    object creation, not silently at the first validation call.

    Attributes
    ----------
    score_threshold:
        Minimum quality score in ``[0.0, 1.0]`` for a response to be
        considered valid by the validator.
    """

    model_config = ConfigDict(frozen=True)

    score_threshold: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Minimum acceptable quality score from the validator LLM.",
    )


# ---------------------------------------------------------------------------
# OutputValidator
# ---------------------------------------------------------------------------


class OutputValidator:
    """
    Validates and optionally refines agent outputs using a dedicated LLM.

    The validator LLM is intentionally **separate** from the agent LLM so
    that a different model (or the same model with different settings) can
    act as an independent quality gate.

    Parameters
    ----------
    llm:
        The LLM to use for validation.  Should support
        ``with_structured_output``.
    prompt_builder:
        A :class:`~reusableagents.prompts.base.PromptBuilder` whose
        ``{original_input}`` and ``{agent_output}`` placeholders will be
        filled at validation time.  Defaults to the built-in validation
        prompt when omitted.
    score_threshold:
        Minimum score for ``is_valid`` to be ``True``.  The LLM sets the
        score itself; this threshold post-processes the decision so that a
        stricter or more lenient bar can be applied without re-prompting.

    Examples
    --------
    ::

        from reusableagents.llm.gemini import create_validator_llm
        from reusableagents.agents.validator import OutputValidator

        validator = OutputValidator(llm=create_validator_llm())
        result = validator.validate(
            original_input="What is 2 + 2?",
            agent_output="The answer is 5.",
        )
        print(result.is_valid)        # False
        print(result.refined_output)  # "The answer is 4."
    """

    def __init__(
        self,
        llm: BaseChatModel,
        prompt_builder: Optional[PromptBuilder] = None,
        score_threshold: float = 0.7,
    ) -> None:
        # Validate score_threshold range via Pydantic before storing.
        _cfg = OutputValidatorConfig(score_threshold=score_threshold)
        if not isinstance(llm, BaseChatModel):
            raise TypeError(
                f"llm must be a BaseChatModel instance, "
                f"got {type(llm).__name__!r}"
            )
        if prompt_builder is not None and not isinstance(prompt_builder, PromptBuilder):
            raise TypeError(
                f"prompt_builder must be a PromptBuilder instance or None, "
                f"got {type(prompt_builder).__name__!r}"
            )
        self._llm = llm
        self._prompt_builder = prompt_builder or _build_default_validation_prompt()
        self._score_threshold = _cfg.score_threshold
        # Bind structured-output schema once so it's reused across calls.
        self._structured_llm = llm.with_structured_output(ValidationResult)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def validate(
        self,
        original_input: str,
        agent_output: str,
        **extra_variables: Any,
    ) -> ValidationResult:
        """
        Evaluate the *agent_output* against the *original_input*.

        When the LLM-assigned score is below :attr:`score_threshold`, the
        ``is_valid`` flag is overridden to ``False`` regardless of what the
        LLM returned, ensuring the threshold is respected even if the LLM
        is inconsistent.

        Parameters
        ----------
        original_input:
            The original user request / query sent to the agent.
        agent_output:
            The final response produced by the ReAct agent.
        **extra_variables:
            Additional variables forwarded to the prompt template.

        Returns
        -------
        ValidationResult
            Structured quality assessment with optional refined output.
        """
        messages = self._prompt_builder.to_messages(
            original_input=original_input,
            agent_output=agent_output,
            **extra_variables,
        )

        logger.debug("Running output validation …")
        try:
            result: ValidationResult = self._structured_llm.invoke(messages)
        except Exception as exc:
            # Graceful degradation: treat as valid when validator itself fails
            # so the agent pipeline doesn't break.
            logger.warning("Validator LLM call failed (%s). Treating output as valid.", exc)
            return ValidationResult(
                is_valid=True,
                score=1.0,
                feedback=f"Validation skipped due to error: {exc}",
                refined_output=None,
            )

        # Enforce the score threshold as a secondary decision gate.
        if result.score < self._score_threshold and result.is_valid:
            logger.debug(
                "Score %.2f is below threshold %.2f – overriding is_valid to False.",
                result.score,
                self._score_threshold,
            )
            result = ValidationResult(
                is_valid=False,
                score=result.score,
                feedback=result.feedback,
                refined_output=result.refined_output,
            )

        logger.debug(
            "Validation complete – is_valid=%s, score=%.2f",
            result.is_valid,
            result.score,
        )
        return result
