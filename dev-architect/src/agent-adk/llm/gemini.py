"""
Gemini LLM factory module.

Creates ``ChatVertexAI`` instances for the agent and validator roles.
Authentication is delegated entirely to Google Cloud Application Default
Credentials (ADC) – no API keys are stored in this code.

Prerequisites
-------------
Run once in your shell before using this library::

    gcloud auth application-default login

or set the ``GOOGLE_APPLICATION_CREDENTIALS`` environment variable to the
path of a service-account key file.
"""

from __future__ import annotations

from langchain_google_vertexai import ChatVertexAI

from config.settings import GeminiConfig


def create_agent_llm(config: GeminiConfig | None = None) -> ChatVertexAI:
    """
    Create the primary LLM used inside the ReAct agent loop.

    Uses Google Cloud ADC for authentication – no API key required.

    Parameters
    ----------
    config:
        :class:`~reusableagents.config.settings.GeminiConfig` instance.
        Falls back to default settings (project ``ai-practice-enterprise-ai``,
        region ``asia-south2``, model ``gemini-2.5-pro``) when omitted.

    Returns
    -------
    ChatVertexAI
        A configured chat model ready for use with LangChain / LangGraph.
    """
    cfg = config or GeminiConfig()
    return ChatVertexAI(
        model_name=cfg.agent_model,
        project=cfg.project_id,
        location=cfg.location,
        temperature=cfg.agent_temperature,
        max_output_tokens=cfg.max_output_tokens,
    )


def create_validator_llm(config: GeminiConfig | None = None) -> ChatVertexAI:
    """
    Create the LLM used exclusively for output validation and refinement.

    Keeping this separate from the agent LLM lets you swap in a lighter /
    cheaper model for validation without affecting agent behaviour.

    Parameters
    ----------
    config:
        :class:`~reusableagents.config.settings.GeminiConfig` instance.
        Falls back to default settings when omitted.

    Returns
    -------
    ChatVertexAI
        A configured chat model ready for structured-output extraction.
    """
    cfg = config or GeminiConfig()
    return ChatVertexAI(
        model_name=cfg.validator_model,
        project=cfg.project_id,
        location=cfg.location,
        temperature=cfg.validator_temperature,
        max_output_tokens=cfg.max_output_tokens,
    )
