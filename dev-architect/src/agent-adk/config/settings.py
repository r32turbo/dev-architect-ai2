"""
Configuration models for the ReAct agent and Gemini LLM.

Both models are *frozen* Pydantic ``BaseModel`` instances so that every field value
is validated at construction time and cannot be mutated afterwards.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class GeminiConfig(BaseModel):
    """
    Configuration for Gemini models hosted on Vertex AI.

    Authentication is handled entirely by Google Cloud Application Default
    Credentials (ADC).  Run ``gcloud auth application-default login`` once
    before using this library.

    All fields are validated by Pydantic at construction time.  The model is
    *frozen* (immutable) to prevent accidental mutation after creation.

    Attributes:
        project_id:            GCP project that owns the Vertex AI endpoint.
                               Must be a non-empty string.
        location:              GCP region for inference (e.g. ``asia-south2``).
                               Must be a non-empty string.
        agent_model:           Model used by the primary ReAct agent.
        validator_model:       Model used for output validation / refinement.
        agent_temperature:     Sampling temperature for the agent LLM in
                               ``[0.0, 2.0]``.  0.0 = deterministic.
        validator_temperature: Sampling temperature for the validator LLM in
                               ``[0.0, 2.0]``.  Usually kept at 0.0.
        max_output_tokens:     Maximum tokens the models may generate (> 0).
    """

    model_config = ConfigDict(frozen=True)

    project_id: str = Field(
        default="ai-practice-enterprise-ai",
        min_length=1,
        description="GCP project ID that owns the Vertex AI endpoint.",
    )
    location: str = Field(
        default="us-central1",
        min_length=1,
        description="GCP region used for Vertex AI inference.",
    )
    agent_model: str = Field(
        default="gemini-1.5-flash",
        min_length=1,
        description="Model name for the primary ReAct agent.",
    )
    validator_model: str = Field(
        default="gemini-1.5-flash",
        min_length=1,
        description="Model name used for output validation and refinement.",
    )
    agent_temperature: float = Field(
        default=0.0,
        ge=0.0,
        le=2.0,
        description="Sampling temperature for the agent LLM.",
    )
    validator_temperature: float = Field(
        default=0.0,
        ge=0.0,
        le=2.0,
        description="Sampling temperature for the validator LLM.",
    )
    max_output_tokens: int = Field(
        default=8192,
        gt=0,
        description="Maximum number of tokens either model may generate per call.",
    )


class AgentConfig(BaseModel):
    """
    Behavioural configuration for ``ReusableReActAgent``.

    The model is *frozen* (immutable) so that a single ``AgentConfig`` can
    safely be shared across multiple agent instances.

    Attributes:
        max_react_iterations:
            Maximum number of *tool-use* iterations the ReAct loop may
            perform before it is forcibly stopped.  Must be ``>= 1``.
        enable_validation:
            Whether to run the ``OutputValidator`` on the agent's final
            response.  Set to ``False`` to skip validation entirely.
        validation_score_threshold:
            Minimum quality score in ``[0.0, 1.0]`` for the validator to
            consider the output acceptable.  Outputs below this threshold
            trigger the refinement step.
        max_refinement_attempts:
            How many times the agent may be re-run with validator feedback
            when the validator does not supply a ``refined_output`` directly.
            Must be ``>= 0`` (0 disables re-run refinement).
    """

    model_config = ConfigDict(frozen=True)

    max_react_iterations: int = Field(
        default=10,
        ge=1,
        description="Maximum tool-call loop iterations before a forced stop.",
    )
    enable_validation: bool = Field(
        default=True,
        description="When False, the OutputValidator is skipped entirely.",
    )
    validation_score_threshold: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Minimum acceptable quality score from the validator LLM.",
    )
    max_refinement_attempts: int = Field(
        default=2,
        ge=0,
        description="Maximum extra agent re-runs triggered when validation fails.",
    )


# ---------------------------------------------------------------------------
# Supervisor
# ---------------------------------------------------------------------------


class ExecutionMode(str, Enum):
    """
    Controls how the :class:`~reusableagents.agents.supervisor.SupervisorAgent`
    schedules calls to its worker agents.

    Attributes
    ----------
    SERIAL:
        Workers are always called one at a time.  The supervisor processes
        each result before deciding on the next step.  Best for tasks with
        strict sequential dependencies.
    PARALLEL:
        The supervisor is prompted to use the ``dispatch_parallel`` tool
        whenever multiple workers can run concurrently.  Workers are
        executed in a ``ThreadPoolExecutor`` for genuine parallelism.
        Best for fan-out / aggregation workflows.
    AUTO:
        The supervisor LLM decides dynamically whether to call workers
        sequentially or in parallel based on task dependencies.  Both
        individual worker tools and ``dispatch_parallel`` are available.
    """

    SERIAL = "serial"
    PARALLEL = "parallel"
    AUTO = "auto"


class SupervisorConfig(BaseModel):
    """
    Behavioural configuration for
    :class:`~reusableagents.agents.supervisor.SupervisorAgent`.

    The model is *frozen* (immutable) and all fields are validated by Pydantic
    at construction time.

    Attributes
    ----------
    execution_mode:
        Controls scheduling of worker agents.  See :class:`ExecutionMode`.
    max_iterations:
        Maximum number of supervisor loop iterations (tool-call rounds)
        before a forced stop.  Maps to
        ``recursion_limit = max_iterations * 2 + 1``.  Must be ``>= 1``.
    max_parallel_workers:
        Maximum number of threads used by the ``dispatch_parallel`` tool
        when running workers concurrently.  Must be ``>= 1``.
    enable_validation:
        Whether the supervisor's synthesized final answer should be reviewed
        by an :class:`~reusableagents.agents.validator.OutputValidator`.
        Defaults to ``False`` to avoid extra latency in multi-agent pipelines.
    max_refinement_attempts:
        How many times the supervisor may be re-invoked with validator
        feedback before accepting the best available answer.  ``0`` disables
        re-run refinement (the validator can still provide a ``refined_output``
        inline).  Must be ``>= 0``.
    """

    model_config = ConfigDict(frozen=True)

    execution_mode: ExecutionMode = Field(
        default=ExecutionMode.AUTO,
        description="Worker scheduling strategy: serial, parallel, or auto.",
    )
    max_iterations: int = Field(
        default=20,
        ge=1,
        description="Maximum supervisor loop iterations before a forced stop.",
    )
    max_parallel_workers: int = Field(
        default=10,
        ge=1,
        description="Max concurrent threads for the dispatch_parallel tool.",
    )
    enable_validation: bool = Field(
        default=False,
        description="When True, an OutputValidator reviews the supervisor's final answer.",
    )
    max_refinement_attempts: int = Field(
        default=1,
        ge=0,
        description="Maximum supervisor re-runs triggered when validation fails.",
    )
