"""Minimal demo UI: submit an incident description, view the diagnosis + trace.

Run with: streamlit run frontend/streamlit_app.py
Expects the FastAPI server to be running (default http://localhost:8000).
"""
import os

import requests
import streamlit as st

st.set_page_config(page_title="DevOps Incident Triage Agent", layout="wide")

API_URL = st.sidebar.text_input("API URL", value=os.environ.get("API_BASE_URL", "http://localhost:8000"))

st.title("DevOps Incident Triage Agent")
st.caption(
    "Describe an incident; the agent investigates using log search, runbook retrieval, "
    "web search, and code execution, then reports a structured diagnosis."
)

incident_description = st.text_area(
    "Incident description",
    placeholder="e.g. checkout-api is returning 503s and payments-service logs show DB timeouts",
    height=100,
)

if st.button("Diagnose", type="primary") and incident_description.strip():
    with st.spinner("Agent investigating..."):
        try:
            response = requests.post(
                f"{API_URL}/diagnose", json={"incident_description": incident_description}, timeout=120
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            st.error(f"Request failed: {exc}")
        else:
            data = response.json()
            result = data["result"]
            diagnosis = result["diagnosis"]

            col1, col2, col3 = st.columns(3)
            col1.metric("Confidence", f"{diagnosis['confidence']:.0%}")
            col2.metric("Latency", f"{data['latency_seconds']:.2f}s")
            col3.metric("Est. cost", f"${data['estimated_cost_usd']:.4f}")

            if diagnosis["insufficient_evidence"]:
                st.warning("Agent hit its iteration cap without strong converging evidence.")

            st.subheader("Root cause")
            st.write(diagnosis["root_cause"])

            st.subheader("Suggested fix")
            st.write(diagnosis["suggested_fix"])

            st.subheader("Evidence trail")
            if diagnosis["evidence_trail"]:
                for item in diagnosis["evidence_trail"]:
                    st.markdown(f"- {item}")
            else:
                st.markdown("_no evidence cited_")

            st.subheader(f"Reasoning trace ({result['iterations_used']} steps)")
            for step in result["reasoning_trace"]:
                status_icon = "❌" if step["tool_failed"] else "✅"
                with st.expander(f"Step {step['step']} {status_icon} — {step['tool_called']}"):
                    st.write("**Thought:**", step["thought"])
                    st.write("**Tool input:**")
                    st.json(step["tool_input"])
                    st.write("**Tool result:**")
                    st.json(step["tool_result"])
