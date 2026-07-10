"""Request/response models for the FastAPI layer."""
from pydantic import BaseModel

from agent.schemas import AgentResult


class DiagnoseRequest(BaseModel):
    incident_description: str


class DiagnoseResponse(BaseModel):
    result: AgentResult
    latency_seconds: float
    estimated_tokens: int
    estimated_cost_usd: float
