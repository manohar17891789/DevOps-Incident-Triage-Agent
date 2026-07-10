"""Keyword/service/time-range search over the synthetic log dataset."""
import json
from datetime import datetime
from pathlib import Path

from tools.schemas import LogEntry, LogSearchInput, LogSearchOutput

LOGS_PATH = Path(__file__).resolve().parent.parent / "data" / "logs" / "synthetic_logs.json"


def _load_logs() -> list[LogEntry]:
    with open(LOGS_PATH) as f:
        raw = json.load(f)
    return [LogEntry(**entry) for entry in raw]


_LOGS_CACHE: list[LogEntry] | None = None


def _get_logs() -> list[LogEntry]:
    global _LOGS_CACHE
    if _LOGS_CACHE is None:
        _LOGS_CACHE = _load_logs()
    return _LOGS_CACHE


def run_log_search(input: LogSearchInput) -> LogSearchOutput:
    entries = _get_logs()

    if input.service:
        entries = [e for e in entries if e.service.lower() == input.service.lower()]

    if input.keyword:
        kw = input.keyword.lower()
        entries = [
            e
            for e in entries
            if kw in e.message.lower()
            or (e.stack_trace and kw in e.stack_trace.lower())
            or (e.error_code and kw in e.error_code.lower())
        ]

    if input.start_time:
        start = datetime.fromisoformat(input.start_time.replace("Z", "+00:00"))
        entries = [e for e in entries if datetime.fromisoformat(e.timestamp.replace("Z", "+00:00")) >= start]

    if input.end_time:
        end = datetime.fromisoformat(input.end_time.replace("Z", "+00:00"))
        entries = [e for e in entries if datetime.fromisoformat(e.timestamp.replace("Z", "+00:00")) <= end]

    entries = sorted(entries, key=lambda e: e.timestamp, reverse=True)
    total_matches = len(entries)

    return LogSearchOutput(success=True, entries=entries[: input.limit], total_matches=total_matches)
