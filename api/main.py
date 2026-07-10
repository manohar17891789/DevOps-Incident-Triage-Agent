"""FastAPI wrapper exposing the triage agent as POST /diagnose."""
import logging
import time

from fastapi import FastAPI, HTTPException
from langchain_community.callbacks import get_openai_callback

from agent.graph import run_agent
from api.schemas import DiagnoseRequest, DiagnoseResponse
from config import settings

logging.basicConfig(level=settings.log_level)
logger = logging.getLogger("triage_agent")

app = FastAPI(title="DevOps Incident Triage Agent")

# gpt-4o-mini pricing per 1M tokens; update if OPENAI_MODEL changes.
PRICE_PER_1M_INPUT_TOKENS = 0.15
PRICE_PER_1M_OUTPUT_TOKENS = 0.60


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/diagnose", response_model=DiagnoseResponse)
def diagnose(request: DiagnoseRequest) -> DiagnoseResponse:
    start = time.perf_counter()
    try:
        with get_openai_callback() as cb:
            result = run_agent(request.incident_description)
    except Exception as exc:
        logger.exception("Agent run failed for incident: %s", request.incident_description)
        raise HTTPException(status_code=502, detail=f"Agent run failed: {exc}") from exc
    latency = time.perf_counter() - start

    estimated_cost = (
        cb.prompt_tokens / 1_000_000 * PRICE_PER_1M_INPUT_TOKENS
        + cb.completion_tokens / 1_000_000 * PRICE_PER_1M_OUTPUT_TOKENS
    )

    logger.info(
        "diagnose complete: iterations=%d latency=%.2fs tokens=%d cost=$%.6f",
        result.iterations_used,
        latency,
        cb.total_tokens,
        estimated_cost,
    )

    return DiagnoseResponse(
        result=result,
        latency_seconds=round(latency, 3),
        estimated_tokens=cb.total_tokens,
        estimated_cost_usd=round(estimated_cost, 6),
    )
