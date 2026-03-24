"""Prompt building abstraction for ReusableReActAgent."""

from typing import Dict, Any, Optional


class PromptBuilder:
    """
    Builder for constructing system and user prompts with template variables.

    Supports variable placeholders like {variable_name} that are resolved
    at runtime via .render_system() and .render_user() methods.

    Examples
    --------
    ::

        prompt = (
            PromptBuilder()
            .add_system("You are a helpful assistant. Today is {date}.", name="persona")
            .add_user("Answer this: {question}", name="question")
        )

        system_text = prompt.render_system(date="2026-03-22")
        user_text = prompt.render_user(question="What is 2+2?")
    """

    def __init__(self):
        """Initialize an empty PromptBuilder."""
        self._system_template: Optional[str] = None
        self._user_template: Optional[str] = None

    def add_system(self, template: str, name: Optional[str] = None) -> "PromptBuilder":
        """
        Set the system prompt template.

        Parameters
        ----------
        template:
            Template string with {variable} placeholders.
        name:
            Optional label for documentation (not used in rendering).

        Returns
        -------
        PromptBuilder
            Self for chaining.
        """
        self._system_template = template
        return self

    def add_user(self, template: str, name: Optional[str] = None) -> "PromptBuilder":
        """
        Set the user prompt template.

        Parameters
        ----------
        template:
            Template string with {variable} placeholders.
        name:
            Optional label for documentation (not used in rendering).

        Returns
        -------
        PromptBuilder
            Self for chaining.
        """
        self._user_template = template
        return self

    def render_system(self, **kwargs: Any) -> str:
        """
        Render the system prompt with provided variables.

        Parameters
        ----------
        **kwargs:
            Variable values to substitute into {variable} placeholders.

        Returns
        -------
        str
            Rendered system prompt.
        """
        if self._system_template is None:
            return ""
        return self._system_template.format(**kwargs)

    def render_user(self, **kwargs: Any) -> str:
        """
        Render the user prompt with provided variables.

        Parameters
        ----------
        **kwargs:
            Variable values to substitute into {variable} placeholders.

        Returns
        -------
        str
            Rendered user prompt.
        """
        if self._user_template is None:
            return ""
        return self._user_template.format(**kwargs)
