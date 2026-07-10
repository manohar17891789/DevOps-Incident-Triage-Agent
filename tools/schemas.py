"""Pydantic input/output contracts shared by all agent tools.

Every tool takes a typed input and returns a typed output plus a bool
`success` flag, so the agent can branch on failure without try/except
sprawl at the call site.
"""
from typing import Literal, Optional

from pydantic import BaseModel, Field


class LogSearchInput(BaseModel):
    keyword: Optional[str] = Field(None, description="Substring to match in message/stack_trace")
    service: Optional[str] = Field(None, description="Filter by service name, e.g. 'checkout-api'")
    start_time: Optional[str] = Field(None, description="ISO8601 lower bound on timestamp")
    end_time: Optional[str] = Field(None, description="ISO8601 upper bound on timestamp")
    limit: int = Field(10, ge=1, le=50)


class LogEntry(BaseModel):
    timestamp: str
    service: str
    level: str
    error_code: Optional[str] = None
    message: str
    stack_trace: Optional[str] = None


class LogSearchOutput(BaseModel):
    success: bool
    entries: list[LogEntry] = Field(default_factory=list)
    total_matches: int = 0
    error: Optional[str] = None


class WebSearchInput(BaseModel):
    query: str


class WebSearchResult(BaseModel):
    title: str
    url: str
    snippet: str


class WebSearchOutput(BaseModel):
    success: bool
    results: list[WebSearchResult] = Field(default_factory=list)
    error: Optional[str] = None


class CodeExecInput(BaseModel):
    code: str = Field(..., description="Short Python snippet to run in an isolated subprocess")
    timeout_seconds: int = Field(5, ge=1, le=30)


class CodeExecOutput(BaseModel):
    success: bool
    stdout: str = ""
    stderr: str = ""
    exit_code: Optional[int] = None
    timed_out: bool = False
    error: Optional[str] = None


class RunbookRetrievalInput(BaseModel):
    query: str
    top_k: int = Field(3, ge=1, le=10)


class RunbookMatch(BaseModel):
    doc_id: str
    title: str
    content: str
    score: float


class RunbookRetrievalOutput(BaseModel):
    success: bool
    matches: list[RunbookMatch] = Field(default_factory=list)
    error: Optional[str] = None


ToolName = Literal["log_search", "web_search", "code_exec", "runbook_retrieval"]
