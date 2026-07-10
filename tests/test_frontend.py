"""Smoke tests for the Streamlit demo UI using streamlit's AppTest harness.

Mocks requests.post so these never hit a real API or network.
"""
from unittest.mock import MagicMock, patch

from streamlit.testing.v1 import AppTest

_FAKE_RESPONSE_JSON = {
    "result": {
        "diagnosis": {
            "root_cause": "DB connection pool exhaustion from nightly batch job",
            "confidence": 0.85,
            "suggested_fix": "Move the batch job to a dedicated connection pool",
            "evidence_trail": ["DB_CONN_TIMEOUT logs at 2026-07-01T03:12:04Z"],
            "insufficient_evidence": False,
        },
        "reasoning_trace": [
            {
                "step": 1,
                "thought": "check recent logs",
                "tool_called": "log_search",
                "tool_input": {"service": "payments-service"},
                "tool_result": {"success": True, "entries": [], "total_matches": 0},
                "tool_failed": False,
            }
        ],
        "iterations_used": 1,
    },
    "latency_seconds": 1.23,
    "estimated_tokens": 500,
    "estimated_cost_usd": 0.0004,
}


def test_app_loads_without_error():
    at = AppTest.from_file("frontend/streamlit_app.py")
    at.run()
    assert not at.exception


def test_diagnose_button_renders_result():
    fake_response = MagicMock()
    fake_response.json.return_value = _FAKE_RESPONSE_JSON
    fake_response.raise_for_status.return_value = None

    with patch("requests.post", return_value=fake_response):
        at = AppTest.from_file("frontend/streamlit_app.py")
        at.run()
        at.text_area[0].set_value("checkout-api throwing 503s")
        at.button[0].click()
        at.run()

    assert not at.exception
    markdown_text = " ".join(m.value for m in at.markdown)
    assert "DB connection pool exhaustion from nightly batch job" in markdown_text
    assert "Move the batch job to a dedicated connection pool" in markdown_text
    subheaders = [s.value for s in at.subheader]
    assert "Reasoning trace (1 steps)" in subheaders
