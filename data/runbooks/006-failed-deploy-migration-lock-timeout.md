# Runbook: Deploy Failure from Long-Running Migration Lock Timeout

**Services affected:** user-service
**Error codes:** DEPLOY_FAILED

## Symptoms
- Rollout stalls/fails during the migration step, not the application
  startup step.
- Database error resembles `LockNotAvailable` / `canceling statement due to
  lock timeout`.
- Table involved has a large row count (millions+).

## Root Cause
The migration (e.g. `ADD COLUMN` with a default, or a new index) requires a
table-level lock that cannot be acquired quickly on a large, actively-written
table, so it hits the statement/lock timeout configured for migrations.

## Resolution
1. Identify the blocking migration and target table from the error.
2. Cancel the stuck migration if it's still holding a lock.
3. Rewrite the migration to avoid a blocking lock: for Postgres, add columns
   without a default in one step, backfill in batches, then add
   `NOT NULL`/default in a follow-up migration; for new indexes, use
   `CREATE INDEX CONCURRENTLY`.

## Prevention
- Require migrations touching tables above a row-count threshold to go
  through a "safe migration" checklist (concurrent index creation, batched
  backfills, no default on large tables in a single step).
