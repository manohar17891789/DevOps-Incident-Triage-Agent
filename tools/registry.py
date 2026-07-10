"""Tool registry + retry-once wrapper used by the agent's call_tool node."""
from dataclasses import dataclass
from typing import Callable

from pydantic import BaseModel

from tools.code_exec import run_code_exec
from tools.log_search import run_log_search
from tools.runbook_retrieval import run_runbook_retrieval
from tools.schemas import (
    CodeExecInput,
    CodeExecOutput,
    LogSearchInput,
    LogSearchOutput,
    RunbookRetrievalInput,
    RunbookRetrievalOutput,
    WebSearchInput,
    WebSearchOutput,
)
from tools.web_search import run_web_search


@dataclass
class ToolSpec:
    input_model: type[BaseModel]
    output_model: type[BaseModel]
    func: Callable[[BaseModel], BaseModel]


TOOL_REGISTRY: dict[str, ToolSpec] = {
    "log_search": ToolSpec(LogSearchInput, LogSearchOutput, run_log_search),
    "web_search": ToolSpec(WebSearchInput, WebSearchOutput, run_web_search),
    "code_exec": ToolSpec(CodeExecInput, CodeExecOutput, run_code_exec),
    "runbook_retrieval": ToolSpec(RunbookRetrievalInput, RunbookRetrievalOutput, run_runbook_retrieval),
}


def call_tool(tool_name: str, raw_input: dict) -> dict:
    """Validate input, run the tool, and retry once on exception.

    Returns a plain dict (the tool's output schema, dumped) so it can be
    stored directly in the agent's reasoning trace. On two consecutive
    failures, returns a `success: False` dict with an `error` message
    instead of raising, so the agent can note the failure and route around
    the tool rather than crashing.
    """
    spec = TOOL_REGISTRY[tool_name]

    last_error: str | None = None
    for _ in range(2):
        try:
            validated_input = spec.input_model(**raw_input)
            output = spec.func(validated_input)
            return output.model_dump()
        except Exception as exc:  # noqa: BLE001 - tool failures must not crash the agent
            last_error = f"{type(exc).__name__}: {exc}"

    return spec.output_model(success=False, error=f"Tool failed after retry: {last_error}").model_dump()
