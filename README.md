# DevOps Incident Triage Agent

An agentic system that diagnoses infrastructure incidents by orchestrating multiple
tools (log search, runbook retrieval, web search, code execution) through a
LangGraph state machine.

> Status: scaffold in progress. This README will be filled in with architecture,
> setup, and example usage as each part of the system is built.

## Stack

- Python 3.11+, FastAPI, LangGraph, FAISS, SQLite, OpenAI (gpt-4o-mini), Docker

## Project layout

```
agent/      LangGraph state machine, reasoning trace + diagnosis schemas
tools/      log_search, web_search, code_exec, runbook_retrieval (+ shared schemas)
api/        FastAPI app exposing POST /diagnose
data/       synthetic logs, runbook markdown docs, seed script
frontend/   demo UI
tests/      unit tests per tool + agent
```

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then add your OPENAI_API_KEY
```
