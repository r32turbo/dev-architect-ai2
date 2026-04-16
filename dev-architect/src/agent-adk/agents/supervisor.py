"""
Supervisor agent module.

``SupervisorAgent`` orchestrates a swarm of worker agents
(:class:`~reusableagents.agents.react_agent.ReusableReActAgent` or nested
``SupervisorAgent`` instances) to complete complex, multi-step tasks.

Architecture
------------
Each worker is registered as a LangChain :class:`~langchain_core.tools.StructuredTool`
so the supervisor LLM—backed by ``langchain.agents.create_agent``—can dispatch
sub-tasks to the right specialist at the right time.

Execution modes
---------------
SERIAL
    One worker is called per turn.  The supervisor processes each result
    before deciding on the next step.  Best for strictly sequential workflows.

PARALLEL
    A ``dispatch_parallel`` tool is provided that accepts a list of
    ``{worker_name, task}`` pairs and executes all of them concurrently via
    :class:`concurrent.futures.ThreadPoolExecutor`.  The supervisor LLM is
    instructed to use this tool when sub-tasks are independent.

AUTO
    Both individual worker tools *and* ``dispatch_parallel`` are available.
    The supervisor LLM decides dynamically which approach to use.

Chaining
--------
``SupervisorAgent`` exposes the same ``run(**prompt_variables) -> AgentResponse``
interface as :class:`~reusableagents.agents.react_agent.ReusableReActAgent`, so
any supervisor can be registered as a worker inside a higher-level supervisor::

    inner = SupervisorAgent(workers=[a, b], llm=llm1, ...)
    outer = SupervisorAgent(
        workers=[
            inner.as_worker("inner_team", "Handles research and analysis"),
            c,
        ],
        llm=llm2,
    )
"""

from __future__ import annotations

import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional, Sequence

from langchain.agents import create_agent
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage, HumanMessage
from langchain_core.tools import BaseTool, StructuredTool
from pydantic import BaseModel, ConfigDict, Field, field_validator

from reusableagents.agents.react_agent import AgentResponse
from reusableagents.agents.validator import OutputValidator
from reusableagents.config.settings import ExecutionMode, SupervisorConfig
from reusableagents.context import AgentContext
from reusableagents.prompts.base import PromptBuilder

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Default supervisor prompt templates
# ---------------------------------------------------------------------------

_DEFAULT_SUPERVISOR_SYSTEM = """\
You are an expert supervisor AI coordinating a team of specialist worker agents.

Your responsibilities
---------------------
1. Analyze the given task carefully and identify all required sub-tasks.
2. Delegate each sub-task to the most appropriate worker agent.
3. Synthesize the workers' outputs into a single, coherent final answer.
4. If a worker's response is inadequate, refine the sub-task and retry.
5. Do NOT answer from your own knowledge when a specialist worker is better suited.\
"""

_DEFAULT_SUPERVISOR_USER = "Task: {task}"


def _build_default_supervisor_prompt() -> PromptBuilder:
    return (
        PromptBuilder()
        .add_system(_DEFAULT_SUPERVISOR_SYSTEM, name="supervisor_role")
        .add_user(_DEFAULT_SUPERVISOR_USER, name="task")
    )


# ---------------------------------------------------------------------------
# Internal Pydantic models for the parallel-dispatch tool
# ---------------------------------------------------------------------------


class _WorkerTask(BaseModel):
    """A single worker + task pair for batch parallel dispatch."""

    worker_name: str = Field(
        description="Exact name of the worker agent to call."
    )
    task: str = Field(
        description="The specific task or question to send to this worker."
    )


class _ParallelDispatchInput(BaseModel):
    """Input schema for the ``dispatch_parallel`` tool."""

    tasks: List[_WorkerTask] = Field(
        min_length=1,
        description=(
            "List of {worker_name, task} pairs to execute concurrently. "
            "Use this when the sub-tasks are independent of one another."
        ),
    )


# ---------------------------------------------------------------------------
# WorkerSpec
# ---------------------------------------------------------------------------


class WorkerSpec(BaseModel):
    """
    Registration of a single worker agent with a :class:`SupervisorAgent`.

    A ``WorkerSpec`` bundles the worker agent with the metadata the supervisor
    LLM needs to decide when and how to call it.

    Attributes
    ----------
    name:
        Unique tool name used by the supervisor LLM.  Must start with a letter
        and contain only letters, digits, and underscores (no spaces).
    description:
        Human-readable explanation of what this worker specialises in.
        Shown verbatim to the supervisor LLM as the tool's description.
    agent:
        The worker agent.  Must expose a ``run(**kwargs) -> AgentResponse``
        callable method.  Accepts either a
        :class:`~reusableagents.agents.react_agent.ReusableReActAgent` or a
        nested :class:`SupervisorAgent` (or any object with a compatible
        ``run()`` signature).
    task_variable:
        The prompt-variable name in the worker's
        :class:`~reusableagents.prompts.base.PromptBuilder` that receives the
        task string dispatched by the supervisor.  Defaults to ``"task"``.
    bound_variables:
        Prompt variables that are always pre-supplied when this worker is
        called.  These are merged with ``{task_variable: task}`` at call time.
        Useful for constants like ``domain``, ``current_date``, etc.

    Examples
    --------
    ::

        WorkerSpec(
            name="math_expert",
            description="Solves arithmetic and algebra problems.",
            agent=math_react_agent,
            task_variable="task",
            bound_variables={"domain": "mathematics", "current_date": "2026-03-22"},
        )
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: str = Field(
        min_length=1,
        description="Unique snake_case tool name for this worker.",
    )
    description: str = Field(
        min_length=1,
        description="What this worker specialises in (shown to the supervisor LLM).",
    )
    agent: Any = Field(
        description="Worker agent with a callable run(**kwargs) -> AgentResponse method.",
    )
    task_variable: str = Field(
        default="task",
        min_length=1,
        description="Prompt variable that receives the supervisor-dispatched task string.",
    )
    bound_variables: Dict[str, Any] = Field(
        default_factory=dict,
        description="Pre-bound prompt variables merged into every worker call.",
    )

    @field_validator("name")
    @classmethod
    def _name_is_valid_identifier(cls, v: str) -> str:
        """Reject names with spaces or non-identifier characters."""
        if not re.match(r"^[a-zA-Z][a-zA-Z0-9_]*$", v):
            raise ValueError(
                f"WorkerSpec.name must start with a letter and contain only "
                f"letters, digits, and underscores; got {v!r}"
            )
        return v

    @field_validator("agent")
    @classmethod
    def _agent_has_run(cls, v: Any) -> Any:
        """Ensure the agent exposes a callable run() method."""
        if not callable(getattr(v, "run", None)):
            raise ValueError(
                f"WorkerSpec.agent must expose a callable 'run' method; "
                f"got {type(v).__name__!r}"
            )
        return v


# ---------------------------------------------------------------------------
# SupervisorAgent
# ---------------------------------------------------------------------------


class SupervisorAgent:
    """
    Orchestrates a swarm of worker agents using ``langchain.agents.create_agent``.

    The supervisor LLM is given the workers as tools and decides which to call,
    in what order, and (in PARALLEL / AUTO mode) which to run concurrently.

    Parameters
    ----------
    workers:
        One or more :class:`WorkerSpec` instances describing the swarm.
        Worker names must be unique.
    llm:
        The LLM that drives the supervisor's reasoning loop.
    prompt_builder:
        A :class:`~reusableagents.prompts.base.PromptBuilder` that defines the
        supervisor's system and user prompt templates.  The worker roster and
        execution-mode instructions are appended to the system prompt
        automatically.  When omitted, a sensible default template is used.
    config:
        :class:`~reusableagents.config.settings.SupervisorConfig` controlling
        execution mode, iteration limits, and validation.  Defaults to AUTO mode
        with 20 supervisor iterations.
    validator:
        Optional :class:`~reusableagents.agents.validator.OutputValidator` that
        reviews the supervisor's final synthesized answer.  Requires
        ``config.enable_validation=True`` to take effect.
    context:
        An optional :class:`~reusableagents.context.AgentContext` carrying
        session metadata, authentication / authorisation info, and shared
        mutable state.  When ``None``, the supervisor creates a fresh context
        automatically on the first ``run()`` call.  The same context is
        forwarded to every worker agent so that state is shared across the
        entire pipeline.  A context may also be passed at ``run()`` time via
        the ``context`` keyword argument (which takes precedence).

    Examples
    --------
    **Serial supervisor** (workers called one at a time)::

        supervisor = SupervisorAgent(
            workers=[math_spec, conv_spec],
            llm=supervisor_llm,
            config=SupervisorConfig(execution_mode=ExecutionMode.SERIAL),
        )
        response = supervisor.run(task="Convert 100 °F to Celsius, square the result.")

    **Parallel supervisor** (independent workers run concurrently)::

        supervisor = SupervisorAgent(
            workers=[weather_spec, stocks_spec, news_spec],
            llm=supervisor_llm,
            config=SupervisorConfig(execution_mode=ExecutionMode.PARALLEL),
        )
        response = supervisor.run(task="Give me today's briefing.")

    **Chained supervisors** (supervisor as a worker in another supervisor)::

        research_team = SupervisorAgent(workers=[web_spec, doc_spec], llm=llm1)
        writing_team  = SupervisorAgent(workers=[draft_spec, edit_spec], llm=llm2)

        top_supervisor = SupervisorAgent(
            workers=[
                research_team.as_worker("research_team", "Gathers and analyses information"),
                writing_team.as_worker("writing_team",   "Drafts and polishes content"),
            ],
            llm=supervisor_llm,
        )
        response = top_supervisor.run(task="Write a research report on quantum computing.")
    """

    def __init__(
        self,
        workers: Sequence[WorkerSpec],
        llm: BaseChatModel,
        prompt_builder: Optional[PromptBuilder] = None,
        config: Optional[SupervisorConfig] = None,
        validator: Optional[OutputValidator] = None,
        extra_tools: Sequence[BaseTool] = (),
        context: Optional[AgentContext] = None,
    ) -> None:
        # ------------------------------------------------------------------
        # Validate constructor arguments eagerly.
        # ------------------------------------------------------------------
        if not isinstance(llm, BaseChatModel):
            raise TypeError(
                f"llm must be a BaseChatModel instance, got {type(llm).__name__!r}"
            )
        if prompt_builder is not None and not isinstance(prompt_builder, PromptBuilder):
            raise TypeError(
                f"prompt_builder must be a PromptBuilder instance or None, "
                f"got {type(prompt_builder).__name__!r}"
            )
        if config is not None and not isinstance(config, SupervisorConfig):
            raise TypeError(
                f"config must be a SupervisorConfig instance or None, "
                f"got {type(config).__name__!r}"
            )
        if validator is not None and not isinstance(validator, OutputValidator):
            raise TypeError(
                f"validator must be an OutputValidator instance or None, "
                f"got {type(validator).__name__!r}"
            )
        _workers = list(workers)
        if not _workers:
            raise ValueError("SupervisorAgent requires at least one WorkerSpec.")
        for w in _workers:
            if not isinstance(w, WorkerSpec):
                raise TypeError(
                    f"All workers must be WorkerSpec instances; "
                    f"got {type(w).__name__!r}"
                )
        # Enforce unique worker names.
        names = [w.name for w in _workers]
        duplicates = sorted({n for n in names if names.count(n) > 1})
        if duplicates:
            raise ValueError(
                f"Worker names must be unique; duplicates found: {duplicates}"
            )
        # Validate extra_tools and guard against reserved / conflicting names.
        _extra_tools = list(extra_tools)
        _bad_extra = [
            type(t).__name__ for t in _extra_tools if not isinstance(t, BaseTool)
        ]
        if _bad_extra:
            raise TypeError(
                f"All extra_tools must be BaseTool instances; "
                f"got invalid types: {_bad_extra}"
            )
        _extra_names = [t.name for t in _extra_tools]
        _clashing = sorted(set(_extra_names) & set(names))
        if _clashing:
            raise ValueError(
                f"extra_tools names clash with worker names: {_clashing}"
            )
        if "dispatch_parallel" in _extra_names:
            raise ValueError(
                "'dispatch_parallel' is a reserved tool name and "
                "cannot be used in extra_tools."
            )
        if context is not None and not isinstance(context, AgentContext):
            raise TypeError(
                f"context must be an AgentContext instance or None, "
                f"got {type(context).__name__!r}"
            )
        # ------------------------------------------------------------------
        self.workers = _workers
        self.llm = llm
        self.prompt_builder = prompt_builder or _build_default_supervisor_prompt()
        self.config = config or SupervisorConfig()
        self.validator = validator
        self.extra_tools = _extra_tools
        self.context: Optional[AgentContext] = context

        # Build a name → spec lookup for efficient access inside tool closures.
        self._worker_map: Dict[str, WorkerSpec] = {w.name: w for w in self.workers}

        # Pre-build all tools once so they are reused across every run() call.
        self._tools: List[BaseTool] = self._build_all_tools()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self, **prompt_variables: Any) -> AgentResponse:
        """
        Run the supervisor and return the synthesized final answer.

        Parameters
        ----------
        **prompt_variables:
            Variables substituted into the supervisor's
            :class:`~reusableagents.prompts.base.PromptBuilder` template.

            A special ``context`` keyword may be passed to supply an
            :class:`~reusableagents.context.AgentContext`.  If neither
            the constructor nor ``run()`` receives a context, one is
            created automatically.  The same context is forwarded to
            every worker agent call so state is shared across the
            pipeline.

        Returns
        -------
        AgentResponse
            The final (possibly validated / refined) answer with metadata.
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

        ctx.record("SupervisorAgent", "started")

        system_prompt = self._build_full_system_prompt(**prompt_variables)
        user_message = self.prompt_builder.render_user(**prompt_variables)

        output, messages = self._invoke_supervisor(system_prompt, user_message)

        if self.validator and self.config.enable_validation:
            response = self._validate_and_refine(
                system_prompt=system_prompt,
                original_input=user_message,
                agent_output=output,
                raw_messages=messages,
            )
        else:
            response = AgentResponse(output=output, raw_messages=messages)

        ctx.record(
            "SupervisorAgent",
            "completed",
            detail=str(response.output)[:200] if response.output else None,
        )

        return response

    def as_worker(
        self,
        name: str,
        description: str,
        task_variable: str = "task",
        bound_variables: Optional[Dict[str, Any]] = None,
    ) -> WorkerSpec:
        """
        Wrap this supervisor as a :class:`WorkerSpec` so it can be registered
        as a worker inside another (higher-level) :class:`SupervisorAgent`.

        Parameters
        ----------
        name:
            Snake-case tool name the outer supervisor will use when dispatching
            tasks to this team.
        description:
            What this team / supervisor specialises in (shown to the outer LLM).
        task_variable:
            Prompt variable in this supervisor's PromptBuilder that receives
            the outer supervisor's task string.
        bound_variables:
            Pre-bound variables passed to this supervisor's PromptBuilder on
            every call from the outer supervisor.

        Returns
        -------
        WorkerSpec
            Ready to be added to another ``SupervisorAgent``'s ``workers`` list.

        Example
        -------
        ::

            inner = SupervisorAgent(workers=[a, b], llm=llm1, ...)
            outer = SupervisorAgent(
                workers=[
                    inner.as_worker("research_team", "Researches and analyses topics"),
                    c_spec,
                ],
                llm=llm2,
            )
        """
        return WorkerSpec(
            name=name,
            description=description,
            agent=self,
            task_variable=task_variable,
            bound_variables=bound_variables or {},
        )

    # ------------------------------------------------------------------
    # Internal: prompt assembly
    # ------------------------------------------------------------------

    def _build_full_system_prompt(self, **prompt_variables: Any) -> str:
        """
        Render the user-supplied system prompt, then append the auto-generated
        worker roster and execution-mode guidance.
        """
        base = self.prompt_builder.render_system(**prompt_variables)
        roster = self._build_worker_roster()
        guidance = self._build_execution_guidance()
        parts = [p for p in (base, roster, guidance) if p.strip()]
        return "\n\n".join(parts)

    def _build_worker_roster(self) -> str:
        lines = ["## Available Worker Agents\n"]
        for spec in self.workers:
            lines.append(f"- **{spec.name}**: {spec.description}")
        return "\n".join(lines)

    def _build_execution_guidance(self) -> str:
        if self.config.execution_mode == ExecutionMode.SERIAL:
            return (
                "## Execution Strategy\n"
                "Call one worker at a time.  Analyze each result before deciding "
                "whether to call another worker or provide the final answer.  "
                "Never call more than one worker per turn."
            )
        if self.config.execution_mode == ExecutionMode.PARALLEL:
            return (
                "## Execution Strategy\n"
                "Maximize efficiency by running independent sub-tasks in parallel.  "
                "Use the ``dispatch_parallel`` tool whenever multiple workers can "
                "operate simultaneously—pass all independent {worker_name, task} "
                "pairs in a single call.  Use individual worker tools only when a "
                "task strictly depends on a previous result."
            )
        # AUTO
        return (
            "## Execution Strategy\n"
            "Choose dynamically: use ``dispatch_parallel`` for independent sub-tasks "
            "and individual worker tools when sequential dependencies exist between steps."
        )

    # ------------------------------------------------------------------
    # Internal: tool construction
    # ------------------------------------------------------------------

    def _build_all_tools(self) -> List[BaseTool]:
        """
        Build the complete list of LangChain tools exposed to the supervisor LLM.

        * One :class:`~langchain_core.tools.StructuredTool` per worker (always present).
        * A ``dispatch_parallel`` tool (present in PARALLEL and AUTO modes).
        * Any caller-supplied ``extra_tools`` (e.g. work-distribution utilities).
        """
        tools: List[BaseTool] = [self._make_worker_tool(spec) for spec in self.workers]
        if self.config.execution_mode in (ExecutionMode.PARALLEL, ExecutionMode.AUTO):
            tools.append(self._make_parallel_dispatch_tool())
        tools.extend(self.extra_tools)
        return tools

    def _make_worker_tool(self, spec: WorkerSpec) -> StructuredTool:
        """Wrap a :class:`WorkerSpec` as a single-task ``StructuredTool``."""

        # Capture spec and self in the default argument to avoid late-binding issues.
        supervisor_ref = self

        def _run(task: str, _spec: WorkerSpec = spec) -> str:
            logger.info(
                "Supervisor → worker %r | task: %.150s",
                _spec.name, task,
            )
            try:
                call_kwargs = {**_spec.bound_variables, _spec.task_variable: task}
                # Forward the supervisor's context to the worker agent.
                if supervisor_ref.context is not None:
                    call_kwargs["context"] = supervisor_ref.context
                response: AgentResponse = _spec.agent.run(**call_kwargs)
                score_str = (
                    f"{response.validation_score:.2f}"
                    if response.validation_score is not None
                    else "n/a"
                )
                logger.info(
                    "Worker %r responded (score=%s): %.150s",
                    _spec.name, score_str, response.output,
                )
                _out = response.output
                if isinstance(_out, BaseModel):
                    return _out.model_dump_json(indent=2)
                return _out if isinstance(_out, str) else str(_out)
            except Exception as exc:
                logger.error("Worker %r raised an error: %s", _spec.name, exc)
                return f"[Error from worker '{_spec.name}': {exc}]"

        # Each worker needs its own uniquely-described input schema.
        # Dynamically create a Pydantic model with the worker name embedded
        # in the field description for clarity in the LLM's tool-call reasoning.
        _task_description = (
            f"The specific task or question to send to the '{spec.name}' worker."
        )

        class _SingleTaskInput(BaseModel):
            task: str = Field(description=_task_description)

        _SingleTaskInput.__name__ = f"_{spec.name}_input"

        return StructuredTool.from_function(
            func=_run,
            name=spec.name,
            description=spec.description,
            args_schema=_SingleTaskInput,
        )

    def _make_parallel_dispatch_tool(self) -> StructuredTool:
        """
        Build the ``dispatch_parallel`` tool that runs multiple workers
        concurrently using :class:`concurrent.futures.ThreadPoolExecutor`.
        """
        worker_map = self._worker_map
        max_workers = self.config.max_parallel_workers
        available_names = list(worker_map.keys())
        supervisor_ref = self

        def _dispatch(tasks: List[_WorkerTask]) -> str:
            # Validate all worker names before spawning threads.
            unknown = [t.worker_name for t in tasks if t.worker_name not in worker_map]
            if unknown:
                return (
                    f"Error: unknown worker name(s) {unknown}. "
                    f"Available workers: {available_names}"
                )

            results: Dict[str, str] = {}
            errors: Dict[str, str] = {}

            with ThreadPoolExecutor(
                max_workers=min(len(tasks), max_workers)
            ) as pool:
                future_to_name = {
                    pool.submit(
                        _call_worker,
                        worker_map[wt.worker_name],
                        wt.task,
                        supervisor_ref.context,
                    ): wt.worker_name
                    for wt in tasks
                }
                for future in as_completed(future_to_name):
                    wname = future_to_name[future]
                    try:
                        results[wname] = future.result()
                    except Exception as exc:
                        errors[wname] = str(exc)
                        logger.error(
                            "Parallel worker %r raised: %s", wname, exc
                        )

            lines = ["## Parallel Execution Results\n"]
            for wt in tasks:
                if wt.worker_name in results:
                    lines.append(
                        f"### {wt.worker_name}\n{results[wt.worker_name]}"
                    )
                else:
                    lines.append(
                        f"### {wt.worker_name}\n"
                        f"[ERROR: {errors.get(wt.worker_name, 'unknown')}]"
                    )
            return "\n\n".join(lines)

        return StructuredTool.from_function(
            func=_dispatch,
            name="dispatch_parallel",
            description=(
                "Execute multiple worker agents concurrently for independent sub-tasks. "
                "Pass a list of {worker_name, task} pairs; all workers run in parallel "
                "and their results are returned together in a single response. "
                f"Valid worker names: {available_names}."
            ),
            args_schema=_ParallelDispatchInput,
        )

    # ------------------------------------------------------------------
    # Internal: graph invocation
    # ------------------------------------------------------------------

    def _invoke_supervisor(
        self,
        system_prompt: str,
        user_message: str,
    ) -> tuple[str, List[BaseMessage]]:
        """Build and invoke the ``create_agent`` supervisor graph."""
        graph = create_agent(
            model=self.llm,
            tools=self._tools,
            system_prompt=system_prompt if system_prompt.strip() else None,
        )

        recursion_limit = self.config.max_iterations * 2 + 1
        logger.debug(
            "Invoking supervisor (workers=%d, mode=%s, recursion_limit=%d)",
            len(self.workers),
            self.config.execution_mode.value,
            recursion_limit,
        )

        result = graph.invoke(
            {"messages": [HumanMessage(content=user_message)]},
            config={"recursion_limit": recursion_limit},
        )

        messages: List[BaseMessage] = result.get("messages", [])
        output = _extract_text(messages)
        return output, messages

    # ------------------------------------------------------------------
    # Internal: validation + refinement
    # ------------------------------------------------------------------

    def _validate_and_refine(
        self,
        system_prompt: str,
        original_input: str,
        agent_output: str,
        raw_messages: List[BaseMessage],
    ) -> AgentResponse:
        """
        Validate the supervisor's synthesized answer and refine if needed.

        Mirrors the same three-strategy approach used in
        :class:`~reusableagents.agents.react_agent.ReusableReActAgent`.
        """
        assert self.validator is not None  # guarded by caller

        validation = self.validator.validate(
            original_input=original_input,
            agent_output=agent_output,
        )
        logger.info(
            "Supervisor validation – is_valid=%s, score=%.2f",
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

        # Strategy 2: re-invoke the supervisor with feedback.
        current_output = agent_output
        current_messages = raw_messages
        attempts = 0

        for attempt in range(1, self.config.max_refinement_attempts + 1):
            logger.info(
                "Re-running supervisor with feedback (attempt %d/%d) …",
                attempt,
                self.config.max_refinement_attempts,
            )
            refinement_input = (
                f"{original_input}\n\n"
                "---\n**Previous attempt (needs improvement)**\n\n"
                f"{current_output}\n\n"
                "---\n**Improvement feedback**\n\n"
                f"{validation.feedback}\n\n"
                "Please provide an improved response that addresses the feedback above."
            )
            current_output, current_messages = self._invoke_supervisor(
                system_prompt, refinement_input
            )
            attempts = attempt

            validation = self.validator.validate(
                original_input=original_input,
                agent_output=current_output,
            )
            logger.info(
                "Supervisor re-validation – is_valid=%s, score=%.2f",
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


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


def _call_worker(spec: WorkerSpec, task: str, context: Optional[AgentContext] = None) -> str:
    """
    Invoke a worker agent and return its output string.

    Used as the callable submitted to :class:`concurrent.futures.ThreadPoolExecutor`
    by the ``dispatch_parallel`` tool.  Any exception propagates back to the
    caller so that ``as_completed`` can capture and log it.

    Parameters
    ----------
    spec:
        The worker specification.
    task:
        The task string to pass to the worker.
    context:
        Optional :class:`AgentContext` forwarded to the worker's ``run()``.
    """
    logger.info("Parallel dispatch → worker %r | task: %.150s", spec.name, task)
    call_kwargs: Dict[str, Any] = {**spec.bound_variables, spec.task_variable: task}
    if context is not None:
        call_kwargs["context"] = context
    response: AgentResponse = spec.agent.run(**call_kwargs)
    _out = response.output
    if isinstance(_out, BaseModel):
        return _out.model_dump_json(indent=2)
    return _out if isinstance(_out, str) else str(_out)


def _extract_text(messages: List[BaseMessage]) -> str:
    """Return the text content of the last message in a message list."""
    if not messages:
        return ""
    last = messages[-1]
    if isinstance(last.content, str):
        return last.content
    if isinstance(last.content, list):
        return "".join(
            c.get("text", "") if isinstance(c, dict) else str(c)
            for c in last.content
        )
    return str(last.content)
