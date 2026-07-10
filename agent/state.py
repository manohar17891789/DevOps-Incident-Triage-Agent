"""LangGraph state for the triage agent."""
from typing import Any, Optional, TypedDict


class AgentState(TypedDict):
    incident_description: str
    reasoning_trace: list[dict[str, Any]]
    iteration: int
    max_iterations: int
    pending_tool_call: Optional[dict[str, Any]]
    diagnosis: Optional[dict[str, Any]]
    route: Optional[str]
    forced_by_cap: bool
