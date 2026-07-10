"""Tests for the LangGraph state machine's control flow, with the LLM stubbed out.

These verify plan -> call_tool -> evaluate -> (loop | finalize) wiring, the
iteration cap fallback, and tool-failure routing -- not actual model
reasoning quality, which needs a real OPENAI_API_KEY to exercise.
"""
import agent.graph as graph_module
from agent.graph import EvaluateDecision, ToolCallPlan, build_graph
from agent.schemas import Diagnosis


class _FakeStructuredLLM:
    def __init__(self, response):
        self._response = response

    def invoke(self, _messages):
        return self._response


class _FakeChatModel:
    def __init__(self, response):
        self._response = response

    def with_structured_output(self, _schema):
        return _FakeStructuredLLM(self._response)


def _stub_llm_sequence(monkeypatch, responses):
    queue = list(responses)

    def _get_chat_model(*_args, **_kwargs):
        return _FakeChatModel(queue.pop(0))

    monkeypatch.setattr(graph_module, "get_chat_model", _get_chat_model)


def _initial_state(max_iterations=6):
    return {
        "incident_description": "checkout-api throwing 503s",
        "reasoning_trace": [],
        "iteration": 0,
        "max_iterations": max_iterations,
        "pending_tool_call": None,
        "diagnosis": None,
        "route": None,
        "forced_by_cap": False,
    }


def test_single_loop_then_finalize(monkeypatch):
    plan1 = ToolCallPlan(
        thought="Check recent logs for the affected service",
        tool_name="log_search",
        tool_input={"service": "checkout-api", "limit": 5},
    )
    evaluate1 = EvaluateDecision(thought="Found a clear pattern", decision="finalize", confidence=0.9)
    final_diagnosis = Diagnosis(
        root_cause="DB connection pool exhaustion from batch job",
        confidence=0.85,
        suggested_fix="Move batch job to a dedicated connection pool",
        evidence_trail=["log entry DB_CONN_TIMEOUT at 2026-07-01T03:12:04Z"],
    )
    _stub_llm_sequence(monkeypatch, [plan1, evaluate1, final_diagnosis])

    app = build_graph()
    final_state = app.invoke(_initial_state())

    assert final_state["iteration"] == 1
    assert len(final_state["reasoning_trace"]) == 1
    assert final_state["reasoning_trace"][0]["tool_called"] == "log_search"
    assert final_state["reasoning_trace"][0]["tool_failed"] is False
    assert final_state["diagnosis"]["root_cause"] == "DB connection pool exhaustion from batch job"
    assert final_state["diagnosis"]["insufficient_evidence"] is False


def test_loops_twice_before_finalizing(monkeypatch):
    plan1 = ToolCallPlan(thought="check logs", tool_name="log_search", tool_input={"keyword": "OOM_KILLED"})
    evaluate1 = EvaluateDecision(thought="need more evidence", decision="continue", confidence=0.4)
    plan2 = ToolCallPlan(
        thought="check runbooks", tool_name="runbook_retrieval", tool_input={"query": "OOM unbounded cache"}
    )
    evaluate2 = EvaluateDecision(thought="matches a known runbook", decision="finalize", confidence=0.8)
    final_diagnosis = Diagnosis(
        root_cause="Unbounded LRU cache causing OOMKill",
        confidence=0.8,
        suggested_fix="Bound the cache with max_size and TTL",
        evidence_trail=["OOM_KILLED log", "runbook 003"],
    )
    _stub_llm_sequence(monkeypatch, [plan1, evaluate1, plan2, evaluate2, final_diagnosis])

    app = build_graph()
    final_state = app.invoke(_initial_state())

    assert final_state["iteration"] == 2
    assert [s["tool_called"] for s in final_state["reasoning_trace"]] == ["log_search", "runbook_retrieval"]
    assert final_state["diagnosis"]["root_cause"] == "Unbounded LRU cache causing OOMKill"


def test_iteration_cap_forces_finalize_without_second_evaluate_llm_call(monkeypatch):
    plan_calls = [
        ToolCallPlan(thought=f"attempt {i}", tool_name="log_search", tool_input={"keyword": "nonexistent"})
        for i in range(2)
    ]
    # The agent still wants to keep going after the LLM's own judgment, but
    # hitting max_iterations=2 must force finalize on the *second* evaluate
    # regardless -- so only one EvaluateDecision is stubbed (for the first
    # evaluate, at iteration=1 < 2); the second evaluate call must skip the
    # LLM entirely because the cap is enforced by iteration count alone.
    evaluate1 = EvaluateDecision(thought="want more evidence", decision="continue", confidence=0.3)
    final_diagnosis = Diagnosis(
        root_cause="unclear",
        confidence=0.9,
        suggested_fix="gather more data",
        evidence_trail=[],
    )
    _stub_llm_sequence(monkeypatch, [plan_calls[0], evaluate1, plan_calls[1], final_diagnosis])

    app = build_graph()
    final_state = app.invoke(_initial_state(max_iterations=2))

    assert final_state["iteration"] == 2
    assert final_state["diagnosis"]["insufficient_evidence"] is True
    assert final_state["diagnosis"]["confidence"] <= 0.3


def test_failed_tool_call_is_marked_and_does_not_crash(monkeypatch):
    plan1 = ToolCallPlan(
        thought="try log search with a bad keyword type",
        tool_name="log_search",
        tool_input={"limit": "not-a-number"},
    )
    evaluate1 = EvaluateDecision(thought="that failed, try something else", decision="finalize", confidence=0.2)
    final_diagnosis = Diagnosis(
        root_cause="insufficient evidence after tool failure",
        confidence=0.2,
        suggested_fix="retry with corrected tool input",
        evidence_trail=[],
    )
    _stub_llm_sequence(monkeypatch, [plan1, evaluate1, final_diagnosis])

    app = build_graph()
    final_state = app.invoke(_initial_state())

    assert final_state["reasoning_trace"][0]["tool_failed"] is True
    assert final_state["diagnosis"] is not None
