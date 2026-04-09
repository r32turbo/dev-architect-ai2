"""
AgentContext – Context management for agents.

Provides a context object to track agent execution state, record events,
and share data between agents.
"""

from __future__ import annotations

from typing import Any


class AgentContext:
    """
    Context object for agent execution.
    
    Manages shared state, event recording, and communication between agents.
    """

    def __init__(self):
        """Initialize agent context with empty state and event log."""
        self.state: dict[str, Any] = {}
        self.events: list[dict[str, Any]] = []

    def set_state(self, key: str, value: Any) -> None:
        """
        Set a value in the context state.
        
        Args:
            key: The state key (supports dot notation for nested access)
            value: The value to set
        """
        keys = key.split(".")
        current = self.state
        
        # Navigate/create nested structure
        for k in keys[:-1]:
            if k not in current:
                current[k] = {}
            current = current[k]
        
        # Set the final value
        current[keys[-1]] = value

    def get_state(self, key: str, default: Any = None) -> Any:
        """
        Get a value from the context state.
        
        Args:
            key: The state key (supports dot notation for nested access)
            default: Default value if key not found
            
        Returns:
            The state value or default
        """
        keys = key.split(".")
        current = self.state
        
        for k in keys:
            if isinstance(current, dict) and k in current:
                current = current[k]
            else:
                return default
        
        return current

    def record(self, agent_name: str, event: str, **details) -> None:
        """
        Record an event in the execution log.
        
        Args:
            agent_name: Name of the agent recording the event
            event: Event type/name
            **details: Additional event details
        """
        self.events.append({
            "agent_name": agent_name,
            "event": event,
            **details
        })

    def get_events(self, agent_name: str | None = None) -> list[dict[str, Any]]:
        """
        Get recorded events, optionally filtered by agent name.
        
        Args:
            agent_name: Optional filter by agent name
            
        Returns:
            List of events
        """
        if agent_name is None:
            return self.events
        return [e for e in self.events if e.get("agent_name") == agent_name]
