import os

import pytest

from tools.code_exec import run_code_exec
from tools.log_search import run_log_search
from tools.registry import call_tool
from tools.schemas import CodeExecInput, LogSearchInput, WebSearchInput
from tools.web_search import run_web_search


def test_log_search_by_keyword():
    result = run_log_search(LogSearchInput(keyword="OOM_KILLED", limit=10))
    assert result.success
    assert result.total_matches >= 1
    assert all(e.error_code == "OOM_KILLED" for e in result.entries)


def test_log_search_by_service_and_limit():
    result = run_log_search(LogSearchInput(service="payments-service", limit=2))
    assert result.success
    assert len(result.entries) == 2
    assert all(e.service == "payments-service" for e in result.entries)


def test_log_search_by_time_range():
    result = run_log_search(
        LogSearchInput(start_time="2026-07-06T00:00:00Z", end_time="2026-07-06T23:59:59Z", limit=50)
    )
    assert result.success
    assert all(e.timestamp.startswith("2026-07-06") for e in result.entries)


def test_log_search_no_match_returns_empty_not_error():
    result = run_log_search(LogSearchInput(keyword="totally-nonexistent-keyword-xyz"))
    assert result.success
    assert result.entries == []
    assert result.total_matches == 0


def test_web_search_known_category():
    result = run_web_search(WebSearchInput(query="connection pool exhaustion"))
    assert result.success
    assert len(result.results) >= 1


def test_web_search_unknown_category_returns_placeholder():
    result = run_web_search(WebSearchInput(query="zzz-nothing-matches-zzz"))
    assert result.success
    assert result.results[0].url == ""


def test_code_exec_success():
    result = run_code_exec(CodeExecInput(code="print(1 + 1)"))
    assert result.success
    assert result.stdout.strip() == "2"
    assert result.exit_code == 0


def test_code_exec_error_captured_not_raised():
    result = run_code_exec(CodeExecInput(code="raise ValueError('boom')"))
    assert not result.success
    assert "ValueError" in result.stderr
    assert result.exit_code != 0


def test_code_exec_timeout():
    result = run_code_exec(CodeExecInput(code="import time; time.sleep(5)", timeout_seconds=1))
    assert not result.success
    assert result.timed_out


def test_registry_call_tool_valid_input():
    output = call_tool("log_search", {"service": "gateway", "limit": 3})
    assert output["success"]
    assert len(output["entries"]) <= 3


def test_registry_call_tool_retries_then_reports_failure(monkeypatch):
    def always_fails(_input):
        raise RuntimeError("simulated tool crash")

    from tools.registry import TOOL_REGISTRY

    monkeypatch.setattr(TOOL_REGISTRY["web_search"], "func", always_fails)
    output = call_tool("web_search", {"query": "anything"})
    assert output["success"] is False
    assert "simulated tool crash" in output["error"]


@pytest.mark.skipif(not os.environ.get("OPENAI_API_KEY"), reason="requires OPENAI_API_KEY for embeddings")
def test_runbook_retrieval_returns_relevant_doc():
    from tools.runbook_retrieval import run_runbook_retrieval
    from tools.schemas import RunbookRetrievalInput

    result = run_runbook_retrieval(RunbookRetrievalInput(query="OOMKilled unbounded cache", top_k=3))
    assert result.success
    assert any("memory" in m.doc_id or "oom" in m.content.lower() for m in result.matches)
