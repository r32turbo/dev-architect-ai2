"""Configuration settings for ReusableReActAgent."""

from pydantic import BaseModel, Field


class AgentConfig(BaseModel):
    """
    Behavioural settings for ReusableReActAgent.

    Attributes
    ----------
    max_react_iterations:
        Maximum number of ReAct loop iterations before forced stop.
        Default is 10.
    enable_validation:
        Whether to enable output validation. Default is False.
    max_refinement_attempts:
        Maximum number of refinement attempts after validation fails.
        Default is 3.
    """

    max_react_iterations: int = Field(default=10, ge=1)
    enable_validation: bool = Field(default=False)
    max_refinement_attempts: int = Field(default=3, ge=0)
