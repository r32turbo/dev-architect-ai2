"""
Agent execution context module.

Provides a shared :class:`AgentContext` object that flows through every agent
in a multi-agent pipeline, carrying session metadata, authentication /
authorisation information, arbitrary key–value state, and execution history.

Design goals
------------
- **Shared state** – the supervisor passes the same ``AgentContext`` to every
  worker agent so they can read and write shared data.
- **Auto-creation** – when no context is supplied, one is created
  automatically with sensible defaults.
- **Immutable identity, mutable state** – session and auth information are
  frozen after construction; the ``state`` dict and ``history`` list are
  mutable so agents can collaborate.
- **Serialisable** – the entire context can be exported to a dict via
  ``model_dump()`` for logging, persistence, or transport.

Typical usage
-------------
::

    from reusableagents.context import AgentContext, SessionInfo, AuthInfo

    ctx = AgentContext(
        session=SessionInfo(session_id="abc-123", metadata={"source": "api"}),
        auth=AuthInfo(user_id="u-42", roles=["admin"], permissions=["read", "write"]),
        state={"language": "en"},
    )

    response = agent.run(context=ctx, question="What is 2 + 2?")

    # After the run, inspect shared state written by the agent:
    print(ctx.state)
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# SessionInfo
# ---------------------------------------------------------------------------


class SessionInfo(BaseModel):
    """
    Metadata about the current execution session.

    A *session* groups one or more agent runs that belong to the same
    logical conversation or workflow.  The ``session_id`` is generated
    automatically when omitted, so callers only need to supply one when
    resuming an existing session.

    Attributes
    ----------
    session_id:
        A globally unique identifier for the session.  Auto-generated as a
        UUID-4 string when not provided.
    created_at:
        UTC timestamp of when this session was created.  Defaults to *now*.
    metadata:
        Arbitrary key–value pairs attached to the session (e.g. ``source``,
        ``client_version``, ``request_id``).
    """

    model_config = ConfigDict(frozen=True)

    session_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        min_length=1,
        description="Unique identifier for this session (auto-generated UUID-4).",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp of session creation.",
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Arbitrary session-level metadata.",
    )


# ---------------------------------------------------------------------------
# AuthInfo
# ---------------------------------------------------------------------------


class AuthInfo(BaseModel):
    """
    Authentication and authorisation information for the current user or
    service identity.

    This model captures *who* is making the request and *what* they are
    allowed to do.  Agents can inspect this to enforce access-control rules
    or to tailor responses based on the caller's identity.

    Attributes
    ----------
    user_id:
        Unique identifier of the authenticated user or service account.
        ``None`` when running in an unauthenticated / anonymous context.
    roles:
        Role-based access-control labels (e.g. ``["admin", "editor"]``).
        Empty list means no specific roles are assigned.
    permissions:
        Fine-grained permission strings (e.g. ``["read", "write", "delete"]``).
        Empty list means no explicit permissions beyond the defaults.
    token:
        An opaque bearer token or API key that agents may forward to
        downstream services.  ``None`` when not applicable.  Marked as
        ``exclude=True`` so it is **not** included in ``model_dump()`` /
        ``model_dump_json()`` by default, preventing accidental leakage.
    extra:
        Arbitrary authentication-related metadata (e.g. ``tenant_id``,
        ``org_name``, ``ip_address``).
    """

    model_config = ConfigDict(frozen=True)

    user_id: Optional[str] = Field(
        default=None,
        description="Unique identifier of the authenticated user or service account.",
    )
    roles: List[str] = Field(
        default_factory=list,
        description="Role-based access-control labels.",
    )
    permissions: List[str] = Field(
        default_factory=list,
        description="Fine-grained permission strings.",
    )
    token: Optional[str] = Field(
        default=None,
        exclude=True,
        description="Bearer token or API key (excluded from serialisation).",
    )
    extra: Dict[str, Any] = Field(
        default_factory=dict,
        description="Arbitrary authentication metadata.",
    )

    # Convenience helpers ------------------------------------------------

    def has_role(self, role: str) -> bool:
        """Return ``True`` if the given role is present."""
        return role in self.roles

    def has_permission(self, permission: str) -> bool:
        """Return ``True`` if the given permission is present."""
        return permission in self.permissions


# ---------------------------------------------------------------------------
# HistoryEntry
# ---------------------------------------------------------------------------


class HistoryEntry(BaseModel):
    """
    A single entry in the execution history recorded on the context.

    Each time an agent starts or completes a run, a ``HistoryEntry`` is
    appended to :attr:`AgentContext.history` so that downstream agents
    (or post-processing code) can inspect what happened earlier in the
    pipeline.

    Attributes
    ----------
    agent_name:
        Human-readable label identifying the agent that produced this entry.
    timestamp:
        UTC timestamp of when this entry was recorded.
    event:
        Short tag describing the event (e.g. ``"started"``, ``"completed"``,
        ``"error"``).
    detail:
        Optional free-form detail string (e.g. a summary of the output or
        error message).
    """

    agent_name: str = Field(
        min_length=1,
        description="Label identifying the agent.",
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp of this history entry.",
    )
    event: str = Field(
        min_length=1,
        description="Short event tag (e.g. 'started', 'completed', 'error').",
    )
    detail: Optional[str] = Field(
        default=None,
        description="Free-form detail string.",
    )


# ---------------------------------------------------------------------------
# AgentContext
# ---------------------------------------------------------------------------


class AgentContext(BaseModel):
    """
    Shared execution context that flows through every agent in a pipeline.

    ``AgentContext`` is the single object that a :class:`SupervisorAgent`
    passes to each worker and that each
    :class:`~reusableagents.agents.react_agent.ReusableReActAgent` can read
    from and write to during its ``run()`` call.

    **Immutable parts** – ``session`` and ``auth`` are frozen Pydantic models;
    they cannot be mutated after construction.

    **Mutable parts** – ``state`` (a dict) and ``history`` (a list) are
    deliberately mutable so that agents can share data and record their
    execution trace.

    Attributes
    ----------
    session:
        :class:`SessionInfo` with session-level metadata.  Auto-created with
        defaults when omitted.
    auth:
        :class:`AuthInfo` with authentication and authorisation data.
        Auto-created with empty / anonymous defaults when omitted.
    state:
        A mutable ``Dict[str, Any]`` for inter-agent communication.  Agents
        can read from and write to this dict freely.  The supervisor does
        **not** clear it between worker calls, so state accumulates across
        the pipeline.
    history:
        A mutable list of :class:`HistoryEntry` objects that records the
        execution trace.  Agents append entries as they start and finish
        work.
    parent_run_id:
        Optional identifier linking this context to an outer orchestration
        run (e.g. a trace ID from an observability platform).

    Examples
    --------
    ::

        ctx = AgentContext(
            session=SessionInfo(metadata={"channel": "web"}),
            auth=AuthInfo(user_id="u-1", roles=["viewer"]),
            state={"language": "en", "max_results": 10},
        )

        # Pass to an agent
        response = agent.run(context=ctx, question="Hello!")

        # Read state written by the agent
        print(ctx.state)

        # Inspect execution history
        for entry in ctx.history:
            print(entry.agent_name, entry.event, entry.detail)
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    session: SessionInfo = Field(
        default_factory=SessionInfo,
        description="Session metadata (frozen after construction).",
    )
    auth: AuthInfo = Field(
        default_factory=AuthInfo,
        description="Authentication and authorisation information (frozen).",
    )
    state: Dict[str, Any] = Field(
        default_factory=dict,
        description="Mutable shared state for inter-agent communication.",
    )
    history: List[HistoryEntry] = Field(
        default_factory=list,
        description="Execution trace recorded by agents.",
    )
    parent_run_id: Optional[str] = Field(
        default=None,
        description="Optional trace/run ID linking to an outer orchestration system.",
    )

    # ---- convenience helpers -------------------------------------------

    def record(
        self,
        agent_name: str,
        event: str,
        detail: Optional[str] = None,
    ) -> None:
        """
        Append a :class:`HistoryEntry` to the execution history.

        Parameters
        ----------
        agent_name:
            Label of the agent recording this event.
        event:
            Short tag (e.g. ``"started"``, ``"completed"``).
        detail:
            Optional descriptive string.
        """
        self.history.append(
            HistoryEntry(agent_name=agent_name, event=event, detail=detail)
        )
        logger.debug(
            "Context history: %s → %s%s",
            agent_name,
            event,
            f" ({detail[:80]}…)" if detail and len(detail) > 80 else (f" ({detail})" if detail else ""),
        )

    def get_state(self, key: str, default: Any = None) -> Any:
        """Retrieve a value from the shared state dict."""
        return self.state.get(key, default)

    def set_state(self, key: str, value: Any) -> None:
        """Set a value in the shared state dict."""
        self.state[key] = value
