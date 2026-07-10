"""Seeds the `logs` table from data/logs/synthetic_logs.json.

Safe to call repeatedly: no-ops if the table already has rows, unless
force=True. Run directly (`python -m data.seed_db`) to force a reseed, or
let tools.log_search seed it lazily on first use.
"""
import json
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from data.db import engine
from data.models import Base, LogEntryModel

LOGS_PATH = Path(__file__).resolve().parent / "logs" / "synthetic_logs.json"


def seed(force: bool = False) -> int:
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        if force:
            session.query(LogEntryModel).delete()
        elif session.execute(select(func.count()).select_from(LogEntryModel)).scalar_one() > 0:
            return 0

        with open(LOGS_PATH) as f:
            raw = json.load(f)
        session.add_all(LogEntryModel(**entry) for entry in raw)
        session.commit()
        return len(raw)


if __name__ == "__main__":
    count = seed(force=True)
    print(f"Seeded {count} log entries into {engine.url}")
