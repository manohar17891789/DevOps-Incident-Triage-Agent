"""Pydantic models for the agent's reasoning trace and final diagnosis."""
from typing import Any, Optional

from pydantic import BaseModel, Field

from tools.schemas import ToolName


class ReasoningStep(BaseModel):
    step: int
    thought: str
    tool_called: Optional[ToolName] = None
    tool_input: Optional[dict[str, Any]] = None
    tool_result: Optional[dict[str, Any]] = None
    tool_failed: bool = False


class Diagnosis(BaseModel):
    root_cause: str
    confidence: float = Field(ge=0.0, le=1.0)
    suggested_fix: str
    evidence_trail: list[str] = Field(default_factory=list)
    insufficient_evidence: bool = False


class AgentResult(BaseModel):
    diagnosis: Diagnosis
    reasoning_trace: list[ReasoningStep]
    iterations_used: int
