"""Output validation for ReusableReActAgent."""

from typing import Optional, Any
from pydantic import BaseModel, Field


class ValidationResult(BaseModel):
    """Result of output validation."""

    is_valid: bool = Field(description="Whether output passed validation.")
    score: float = Field(ge=0.0, le=1.0, description="Validation score in [0, 1].")
    feedback: Optional[str] = Field(default=None, description="Validation feedback.")
    refined_output: Optional[str] = Field(
        default=None, description="Validator-supplied refined output (optional)."
    )


class OutputValidator:
    """
    Optional validator that reviews agent output after ReAct loop completes.

    When validation fails, can either supply a ready-made refined_output
    or signal that the agent should re-run with corrective feedback.

    Parameters
    ----------
    validator_llm:
        Optional LLM to use for validation. If None, validation is skipped.
    """

    def __init__(self, validator_llm: Optional[Any] = None):
        """Initialize the validator."""
        self.validator_llm = validator_llm

    def validate(
        self,
        original_input: str,
        agent_output: str,
    ) -> ValidationResult:
        """
        Validate the agent output.

        Parameters
        ----------
        original_input:
            The original user question/input.
        agent_output:
            The output produced by the ReAct agent.

        Returns
        -------
        ValidationResult
            Validation result including score, feedback, and optional refined output.
        """
        if self.validator_llm is None:
            return ValidationResult(is_valid=True, score=1.0, feedback="No validator configured.")

        # Placeholder: in a full implementation, this would call the validator LLM
        return ValidationResult(is_valid=True, score=1.0, feedback="Validation passed.")
