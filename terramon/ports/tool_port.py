"""Tool port — protocol for agent tools (web_search, web_fetch, etc.).

Phase 12 (Agents & Tools): agents delegate tool execution to concrete
implementations behind this port. A ToolPort provides a name, description,
and a run() method.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass
class ToolResult:
    """Result of executing a tool."""

    success: bool
    output: str
    error: str | None = None


class ToolPort(Protocol):
    """Protocol for an agent tool.

    Each tool has:
        name: Short identifier (e.g. "web_search").
        description: Human-readable description for the LLM to decide
                     when to use this tool.
    """

    name: str
    description: str

    def run(self, **kwargs: Any) -> ToolResult:
        """Execute the tool with the given keyword arguments.

        Returns a ToolResult with the output text or error description.
        """
        ...
