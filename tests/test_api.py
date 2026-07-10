from fastapi.testclient import TestClient

import api.main as api_main
from agent.schemas import AgentResult, Diagnosis, ReasoningStep


def _fake_result() -> AgentResult:
    return AgentResult(
        diagnosis=Diagnosis(
            root_cause="DB connection pool exhaustion from nightly batch job",
            confidence=0.85,
            suggested_fix="Move the batch job to a dedicated connection pool",
            evidence_trail=["DB_CONN_TIMEOUT logs at 2026-07-01T03:12:04Z", "runbook 001"],
        ),
        reasoning_trace=[
            ReasoningStep(
                step=1,
                thought="check recent logs for the service",
                tool_called="log_search",
                tool_input={"service": "payments-service"},
                tool_result={"success": True, "entries": [], "total_matches": 0},
                tool_failed=False,
            )
        ],
        iterations_used=1,
    )


def test_health():
    client = TestClient(api_main.app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_diagnose_returns_structured_result_and_metrics(monkeypatch):
    monkeypatch.setattr(api_main, "run_agent", lambda incident_description: _fake_result())

    client = TestClient(api_main.app)
    response = client.post("/diagnose", json={"incident_description": "checkout-api throwing 503s"})

    assert response.status_code == 200
    body = response.json()
    assert body["result"]["diagnosis"]["root_cause"].startswith("DB connection pool exhaustion")
    assert len(body["result"]["reasoning_trace"]) == 1
    assert body["latency_seconds"] >= 0
    assert "estimated_tokens" in body
    assert "estimated_cost_usd" in body


def test_diagnose_returns_502_on_agent_failure(monkeypatch):
    def _raise(_incident_description):
        raise RuntimeError("simulated agent crash")

    monkeypatch.setattr(api_main, "run_agent", _raise)

    client = TestClient(api_main.app)
    response = client.post("/diagnose", json={"incident_description": "anything"})

    assert response.status_code == 502
    assert "simulated agent crash" in response.json()["detail"]
