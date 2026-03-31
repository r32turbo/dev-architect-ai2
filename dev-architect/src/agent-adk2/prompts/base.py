"""
Prompt abstraction layer.

Provides a layered system for building structured prompts from named
constituent parts, with safe variable substitution and distinct
system / user sections.

Key classes
-----------
PromptPart     – a single piece of text that supports ``{variable}`` substitution.
PromptSection  – an ordered collection of PromptParts joined by a separator.
PromptBuilder  – combines a system PromptSection and a user PromptSection into
                 a complete, renderable prompt.

Typical usage
-------------
::

    from reusableagents.prompts.base import PromptBuilder

    builder = (
        PromptBuilder()
        .add_system(
            "You are an expert {domain} analyst.",
            name="persona",
        )
        .add_system(
            "Always respond in {language} and cite your sources.",
            name="style_rules",
        )
        .add_user(
            "Task: {task}",
            name="task",
        )
        .add_user(
            "Background context:\\n{context}",
            name="context",
        )
    )

    messages = builder.to_messages(
        domain="financial",
        language="English",
        task="Summarise Q3 earnings",
        context="Revenue grew 12 % YoY.",
    )
"""

from __future__ import annotations

import copy
from typing import Any, Dict, List, Optional

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from pydantic import BaseModel, ConfigDict, Field, field_validator


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


class _SafeFormatMap(dict):
    """
    A dict subclass used with ``str.format_map`` that leaves any key that is
    not present in the supplied mapping unchanged rather than raising
    ``KeyError``.

    Example::

        "{name} is {age}".format_map(_SafeFormatMap({"name": "Alice"}))
        # → "Alice is {age}"
    """

    def __missing__(self, key: str) -> str:  # noqa: D105
        return f"{{{key}}}"


# ---------------------------------------------------------------------------
# PromptPart
# ---------------------------------------------------------------------------


class PromptPart(BaseModel):
    """
    A single, named constituent of a prompt.

    The ``content`` field is a plain Python f-string–style template that uses
    ``{variable_name}`` placeholders.  Substitution is *safe*: unresolved
    placeholders are left in the output as-is instead of raising an error.

    All fields are validated by Pydantic.  Assignment validation is enabled so
    that updates via :meth:`PromptSection.replace` are also validated.

    Parameters
    ----------
    content:
        The template text.  Must be a non-empty string.  May contain
        ``{variable}`` placeholders.
    name:
        An optional identifier used to look up or replace this part later
        via :meth:`PromptSection.replace` / :meth:`PromptSection.remove`.
        When provided, must be a non-empty, non-whitespace string.

    Examples
    --------
    ::

        part = PromptPart(content="Hello, {name}!  Today is {date}.", name="greeting")
        part.render({"name": "Alice"})          # "Hello, Alice!  Today is {date}."
        part.render({"name": "Alice", "date": "Monday"})  # "Hello, Alice!  Today is Monday."
    """

    model_config = ConfigDict(validate_assignment=True)

    content: str = Field(
        min_length=1,
        description="Template text with optional {variable} placeholders.",
    )
    name: Optional[str] = Field(
        default=None,
        description="Optional identifier for lookup / replacement.",
    )

    @field_validator("name")
    @classmethod
    def _name_not_empty(cls, v: Optional[str]) -> Optional[str]:
        """Reject whitespace-only names so they can't silently fail lookups."""
        if v is not None and not v.strip():
            raise ValueError(
                "'name' must not be an empty or whitespace-only string"
            )
        return v

    # ------------------------------------------------------------------
    def render(self, variables: Optional[Dict[str, Any]] = None) -> str:
        """Return the content with ``{variable}`` placeholders replaced."""
        if not variables:
            return self.content
        return self.content.format_map(_SafeFormatMap(variables))

    def __repr__(self) -> str:  # pragma: no cover
        name_str = f"'{self.name}'" if self.name else "unnamed"
        preview = self.content[:60].replace("\n", "↵")
        ellipsis = "…" if len(self.content) > 60 else ""
        return f"PromptPart({name_str}, '{preview}{ellipsis}')"


# ---------------------------------------------------------------------------
# PromptSection
# ---------------------------------------------------------------------------


class PromptSection:
    """
    An ordered collection of :class:`PromptPart` objects joined by a separator.

    Sections are role-scoped (``"system"`` or ``"user"``) and provide
    mutation helpers so that parts can be added, replaced, or removed by name
    after the initial build.

    Parameters
    ----------
    role:
        The LLM role this section corresponds to (``"system"`` or ``"user"``).
    separator:
        String inserted between parts when rendering (default ``"\\n\\n"``).
    """

    def __init__(self, role: str = "user", separator: str = "\n\n") -> None:
        if role not in ("system", "user"):
            raise ValueError(
                f"role must be 'system' or 'user', got {role!r}"
            )
        if not isinstance(separator, str):
            raise TypeError(
                f"separator must be a str, got {type(separator).__name__!r}"
            )
        self.role = role
        self.separator = separator
        self._parts: List[PromptPart] = []

    # ------------------------------------------------------------------
    # Mutation helpers
    # ------------------------------------------------------------------

    def add(self, content: str, name: Optional[str] = None) -> "PromptSection":
        """Append a new :class:`PromptPart` to this section."""
        self._parts.append(PromptPart(content=content, name=name))
        return self

    def replace(self, name: str, content: str) -> "PromptSection":
        """
        Replace the ``content`` of the first part whose ``name`` matches.

        Raises
        ------
        KeyError
            If no part with the given name exists.
        """
        for part in self._parts:
            if part.name == name:
                part.content = content
                return self
        raise KeyError(f"No PromptPart named '{name}' found in the '{self.role}' section.")

    def remove(self, name: str) -> "PromptSection":
        """Remove all parts whose ``name`` matches."""
        self._parts = [p for p in self._parts if p.name != name]
        return self

    def get(self, name: str) -> Optional[PromptPart]:
        """Return the first part with the given name, or ``None``."""
        return next((p for p in self._parts if p.name == name), None)

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def render(self, variables: Optional[Dict[str, Any]] = None) -> str:
        """
        Render all parts in order, joined by :attr:`separator`.

        Parameters
        ----------
        variables:
            Mapping of ``{variable_name: value}`` pairs for substitution.
        """
        return self.separator.join(p.render(variables) for p in self._parts)

    # ------------------------------------------------------------------
    # Dunder helpers
    # ------------------------------------------------------------------

    @property
    def is_empty(self) -> bool:
        """``True`` if the section has no parts or renders to whitespace."""
        return not self._parts or not self.render().strip()

    def __len__(self) -> int:
        return len(self._parts)

    def __repr__(self) -> str:  # pragma: no cover
        return f"PromptSection(role={self.role!r}, parts={len(self._parts)})"


# ---------------------------------------------------------------------------
# PromptBuilder
# ---------------------------------------------------------------------------


class PromptBuilder:
    """
    The primary abstraction for composing a complete LLM prompt from
    multiple named constituents.

    A ``PromptBuilder`` owns two :class:`PromptSection` objects:

    * ``system`` – rendered into a ``SystemMessage`` (or equivalent).
    * ``user``   – rendered into a ``HumanMessage`` (or equivalent).

    Variable substitution uses ``{variable_name}`` placeholders and is
    *safe*: unknown placeholders are left unchanged.

    Parameters
    ----------
    separator:
        String used to join parts within each section (default ``"\\n\\n"``).

    Examples
    --------
    Build a reusable template::

        builder = (
            PromptBuilder()
            .add_system("You are a {role} specialising in {domain}.", name="persona")
            .add_system("Guidelines:\\n{guidelines}", name="guidelines")
            .add_user("User request: {request}", name="request")
        )

    Render at call-time with concrete values::

        messages = builder.to_messages(
            role="senior data scientist",
            domain="time-series forecasting",
            guidelines="Be concise.  Show your workings.",
            request="Forecast sales for next quarter.",
        )

    Create a variant without touching the original::

        strict_builder = (
            builder.clone()
            .replace_system("guidelines", "Always return JSON.  No prose.")
        )
    """

    def __init__(self, separator: str = "\n\n") -> None:
        if not isinstance(separator, str):
            raise TypeError(
                f"separator must be a str, got {type(separator).__name__!r}"
            )
        self._separator = separator
        self.system = PromptSection(role="system", separator=separator)
        self.user = PromptSection(role="user", separator=separator)

    # ------------------------------------------------------------------
    # Builder-pattern add helpers (return self for chaining)
    # ------------------------------------------------------------------

    def add_system(self, content: str, name: Optional[str] = None) -> "PromptBuilder":
        """
        Append a part to the **system** section.

        Parameters
        ----------
        content:
            Template text.  May contain ``{variable}`` placeholders.
        name:
            Optional identifier so the part can be replaced / removed later.
        """
        self.system.add(content, name)
        return self

    def add_user(self, content: str, name: Optional[str] = None) -> "PromptBuilder":
        """
        Append a part to the **user** section.

        Parameters
        ----------
        content:
            Template text.  May contain ``{variable}`` placeholders.
        name:
            Optional identifier so the part can be replaced / removed later.
        """
        self.user.add(content, name)
        return self

    # ------------------------------------------------------------------
    # In-place mutation helpers (return self for chaining)
    # ------------------------------------------------------------------

    def replace_system(self, name: str, content: str) -> "PromptBuilder":
        """Replace a named part in the system section."""
        self.system.replace(name, content)
        return self

    def replace_user(self, name: str, content: str) -> "PromptBuilder":
        """Replace a named part in the user section."""
        self.user.replace(name, content)
        return self

    def remove_system(self, name: str) -> "PromptBuilder":
        """Remove a named part from the system section."""
        self.system.remove(name)
        return self

    def remove_user(self, name: str) -> "PromptBuilder":
        """Remove a named part from the user section."""
        self.user.remove(name)
        return self

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def render_system(self, **variables: Any) -> str:
        """
        Render the system section as a plain string.

        Parameters
        ----------
        **variables:
            Keyword arguments used for ``{variable}`` substitution.
        """
        return self.system.render(variables)

    def render_user(self, **variables: Any) -> str:
        """
        Render the user section as a plain string.

        Parameters
        ----------
        **variables:
            Keyword arguments used for ``{variable}`` substitution.
        """
        return self.user.render(variables)

    def to_messages(self, **variables: Any) -> List[BaseMessage]:
        """
        Render both sections and return a list of LangChain
        :class:`~langchain_core.messages.BaseMessage` objects.

        A :class:`~langchain_core.messages.SystemMessage` is prepended only
        when the system section is non-empty.  A
        :class:`~langchain_core.messages.HumanMessage` is appended only when
        the user section is non-empty.

        Parameters
        ----------
        **variables:
            Keyword arguments used for ``{variable}`` substitution across
            both sections.

        Returns
        -------
        list[BaseMessage]
            ``[SystemMessage, HumanMessage]`` (one or both may be absent).
        """
        messages: List[BaseMessage] = []

        system_text = self.render_system(**variables)
        if system_text.strip():
            messages.append(SystemMessage(content=system_text))

        user_text = self.render_user(**variables)
        if user_text.strip():
            messages.append(HumanMessage(content=user_text))

        return messages

    # ------------------------------------------------------------------
    # Composition helpers
    # ------------------------------------------------------------------

    def clone(self) -> "PromptBuilder":
        """
        Return a deep copy of this builder.

        Use this to create variants without mutating the original template.
        """
        return copy.deepcopy(self)

    def merge(self, other: "PromptBuilder") -> "PromptBuilder":
        """
        Return a *new* builder whose sections contain the parts of both
        ``self`` and ``other`` (``self``'s parts come first).

        Neither ``self`` nor ``other`` is mutated.
        """
        merged = self.clone()
        for part in other.system._parts:
            merged.system.add(part.content, part.name)
        for part in other.user._parts:
            merged.user.add(part.content, part.name)
        return merged

    # ------------------------------------------------------------------
    # Dunder helpers
    # ------------------------------------------------------------------

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"PromptBuilder("
            f"system_parts={len(self.system)}, "
            f"user_parts={len(self.user)})"
        )
