"""Keyword/service/time-range search over logs stored in the DB.

The `logs` table is lazily seeded from data/logs/synthetic_logs.json on
first use if it's empty, so nothing needs to be run manually for local dev
or tests; docker-compose also runs the seed script explicitly on startup.
"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from data.db import engine
from data.models import LogEntryModel
from data.seed_db import seed
from tools.schemas import LogEntry, LogSearchInput, LogSearchOutput


def run_log_search(input: LogSearchInput) -> LogSearchOutput:
    seed()  # no-op if already seeded

    with Session(engine) as session:
        stmt = select(LogEntryModel)
        if input.service:
            stmt = stmt.where(LogEntryModel.service.ilike(input.service))
        if input.keyword:
            kw = f"%{input.keyword}%"
            stmt = stmt.where(
                LogEntryModel.message.ilike(kw)
                | LogEntryModel.stack_trace.ilike(kw)
                | LogEntryModel.error_code.ilike(kw)
            )
        if input.start_time:
            stmt = stmt.where(LogEntryModel.timestamp >= input.start_time)
        if input.end_time:
            stmt = stmt.where(LogEntryModel.timestamp <= input.end_time)

        rows = session.execute(stmt).scalars().all()

    rows = sorted(rows, key=lambda r: r.timestamp, reverse=True)
    total_matches = len(rows)
    entries = [
        LogEntry(
            timestamp=r.timestamp,
            service=r.service,
            level=r.level,
            error_code=r.error_code,
            message=r.message,
            stack_trace=r.stack_trace,
        )
        for r in rows[: input.limit]
    ]
    return LogSearchOutput(success=True, entries=entries, total_matches=total_matches)
