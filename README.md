# DevOps Incident Triage Agent

An agentic system that diagnoses infrastructure incidents by orchestrating four
tools — log search, runbook retrieval, web search, and code execution — through
a LangGraph state machine, and exposes the result over a FastAPI endpoint with
a Streamlit demo UI on top.

Built as a portfolio project: the priority is a clear architecture and a
demo-able end-to-end flow, not production hardening. See
[What I'd improve](#what-id-improve-with-more-time) for what's deliberately
left out.

## Architecture

```
                        ┌─────────────────────┐
   incident description │  Streamlit frontend │
   ────────────────────►│  (frontend/)         │
                         └──────────┬───────────┘
                                    │ POST /diagnose
                                    ▼
                         ┌──────────────────────┐
                         │   FastAPI (api/)     │
                         │  latency + token/cost │
                         │  logging per request  │
                         └──────────┬───────────┘
                                    │ run_agent()
                                    ▼
                    ┌───────────────────────────────┐
                    │      LangGraph agent (agent/)  │
                    │                                │
                    │   plan ──► call_tool ──► evaluate
                    │    ▲                        │  │
                    │    └────────loop─────────────┘  │
                    │                             finalize
                    └───────────────┬────────────────┘
                                    │ tools.registry.call_tool
                                    │ (validates input, retries once,
                                    │  never raises)
                    ┌───────────────┴────────────────┐
                    ▼               ▼                ▼               ▼
              log_search      web_search        code_exec     runbook_retrieval
              (tools/)        (tools/, stub)     (tools/)      (tools/, FAISS)
                    │                                                 │
                    ▼                                                 ▼
          Postgres/SQLite (data/)                          data/runbooks/*.md
          seeded from synthetic_logs.json                  embedded with OpenAI,
                                                             cached in data/faiss_index/
```

**The agent loop** (`agent/graph.py`):
1. **plan** — the LLM picks exactly one tool + input, given the incident
   description and whatever evidence has been gathered so far.
2. **call_tool** — runs it through `tools/registry.py`, which validates the
   input against the tool's pydantic schema and retries once on any
   exception; a tool that fails twice in a row returns a `success: false`
   result instead of crashing the graph, so the agent can route around it.
   A `ReasoningStep` (`{step, thought, tool_called, tool_input, tool_result,
   tool_failed}`) is appended to the trace either way.
3. **evaluate** — the LLM decides whether there's enough converging evidence
   to finalize, or whether another tool call is needed. Once `iteration >=
   max_agent_iterations` (default 6, `.env`-configurable), this node skips
   the LLM entirely and forces a finalize — the iteration cap is enforced by
   code, not by asking the model nicely.
4. **finalize** — the LLM synthesizes the structured `Diagnosis`
   (`root_cause`, `confidence`, `suggested_fix`, `evidence_trail`). If the
   loop was cut off by the cap rather than the model's own judgment,
   `insufficient_evidence` is set and confidence is capped at 0.3 — an
   honest "I ran out of budget" signal instead of a falsely confident guess.

## Project layout

```
agent/      LangGraph state machine (graph.py), state schema, LLM factory,
            reasoning trace + diagnosis pydantic schemas
tools/      log_search, web_search (stub), code_exec, runbook_retrieval
            (+ shared I/O schemas and the retry-once registry)
api/        FastAPI app: POST /diagnose, GET /health
data/       synthetic logs + runbook markdown docs, SQLAlchemy models,
            seed script
frontend/   Streamlit demo UI
tests/      pytest suite: tools, agent control flow, API, frontend smoke test
```

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then add your OPENAI_API_KEY
```

### Run locally (SQLite, no Docker)

```bash
uvicorn api.main:app --reload
# in another terminal:
streamlit run frontend/streamlit_app.py
```

The `logs` table is seeded automatically from `data/logs/synthetic_logs.json`
on first use (default `DATABASE_URL=sqlite:///./data/incidents.db`). To force
a reseed: `python -m data.seed_db`.

### Run with Docker (Postgres)

```bash
export OPENAI_API_KEY=sk-...
docker compose up --build
```

This brings up Postgres (seeded automatically on API container start) and the
API on `localhost:8000`. Run the Streamlit frontend separately, pointed at
that URL (`API_BASE_URL=http://localhost:8000 streamlit run
frontend/streamlit_app.py`).

### Tests

```bash
pytest
```

20 of 21 tests run without any external dependency (LLM calls are stubbed via
monkeypatched chat model / `run_agent`). The one skipped test
(`test_runbook_retrieval_returns_relevant_doc`) needs a real
`OPENAI_API_KEY` since it exercises actual OpenAI embeddings.

## Example

**Request:**
```bash
curl -X POST http://localhost:8000/diagnose \
  -H "Content-Type: application/json" \
  -d '{"incident_description": "payments-service and checkout-api are throwing DB connection timeout errors around 3am, checkout-api also returning 503s"}'
```

**Response (shape):**
```json
{
  "result": {
    "diagnosis": {
      "root_cause": "The nightly reconciliation batch job holds up to 40 long-running connections against the shared primary-pg pool, starving it for live traffic and causing payments-service and checkout-api to time out.",
      "confidence": 0.85,
      "suggested_fix": "Move the reconciliation job to a dedicated connection pool separate from live traffic; add an alert on pool utilization > 90% for > 60s.",
      "evidence_trail": [
        "log_search: DB_CONN_TIMEOUT on payments-service at 2026-07-01T03:12:04Z, DB_POOL_SATURATED warning at 03:15:02Z",
        "log_search: checkout-api 503 'connection pool exhausted' at 03:13:41Z",
        "runbook_retrieval: 001-db-connection-pool-batch-job.md matches this exact pattern"
      ],
      "insufficient_evidence": false
    },
    "reasoning_trace": [
      {"step": 1, "thought": "Check recent logs for the affected services", "tool_called": "log_search", "tool_input": {"keyword": "DB_CONN_TIMEOUT"}, "tool_result": {"...": "..."}, "tool_failed": false},
      {"step": 2, "thought": "Look for a matching runbook for this failure pattern", "tool_called": "runbook_retrieval", "tool_input": {"query": "DB connection pool exhaustion timeout"}, "tool_result": {"...": "..."}, "tool_failed": false}
    ],
    "iterations_used": 2
  },
  "latency_seconds": 4.21,
  "estimated_tokens": 2140,
  "estimated_cost_usd": 0.000512
}
```

The synthetic dataset (`data/logs/synthetic_logs.json`, `data/runbooks/*.md`)
covers 5 recurring incident types, each with 2 resolution variants, so the
agent has to actually discriminate between similar-looking failures rather
than pattern-match on a single error code:

| Incident type | Example trigger phrase |
|---|---|
| DB connection timeout | "payments-service DB connection timeouts" |
| Memory leak / OOMKill | "recommendation-engine keeps getting OOMKilled" |
| Failed deploy | "user-service rollout failed, readiness probes failing" |
| Auth token expiry | "spike in 401s between internal services" |
| Rate limiting | "checkout-api returning 429s from one client" |

## What I'd improve with more time

- **Real web search.** `tools/web_search.py` is a keyword-matched stub over a
  hardcoded "known issues" dict. Swapping in Tavily/Serper only touches this
  one file, but it's currently not actually searching anything live.
- **Sandbox `code_exec` properly.** It's a bare subprocess with a wall-clock
  timeout — no network isolation, filesystem restriction, or resource limits.
  Fine for a demo where the agent writes its own small snippets, not safe for
  untrusted input.
- **Streaming responses.** `/diagnose` blocks until the whole agent loop
  finishes (multiple LLM round-trips); streaming intermediate reasoning
  steps to the frontend as they happen would make the demo feel much more
  "alive" and is a natural fit for LangGraph's `.stream()` API.
- **Persist reasoning traces.** Right now every `/diagnose` call is
  stateless; storing past incidents + diagnoses (e.g. in the same Postgres
  instance) would let the agent's own history become another retrieval
  source, and would support a "past incidents" view in the UI.
- **Structured output robustness.** `with_structured_output` assumes the LLM
  always returns a schema-valid response; there's no retry-with-repair loop
  if the model returns something that fails pydantic validation on the
  agent's own structured calls (as opposed to tool calls, which are already
  retried).
- **Smarter evaluate node.** It's a single LLM call per loop with no memory
  of *why* it decided to continue last time; a more deliberate approach
  would score evidence quality more explicitly (e.g. "do I have both a log
  match and a runbook match?") rather than relying entirely on the model's
  judgment call.
- **Load testing / concurrency.** No concern has been given to concurrent
  `/diagnose` requests sharing the FAISS index or DB connections under load.
