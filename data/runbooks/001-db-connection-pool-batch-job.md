# Runbook: DB Connection Pool Exhaustion from Nightly Batch Job

**Services affected:** payments-service, checkout-api
**Error codes:** DB_CONN_TIMEOUT, DB_POOL_SATURATED

## Symptoms
- `psycopg2.OperationalError: ... timeout expired` errors from `payments-service`
  around 02:00-04:00 UTC.
- `checkout-api` reports 503s with "connection pool exhausted" shortly after.
- Pool utilization metric pinned at 100% for several minutes.

## Root Cause
The nightly reconciliation batch job (`jobs/reconcile.py`) opens up to 40
long-running connections against the shared `primary-pg` pool (max_connections=100)
and holds them for the duration of the job (10-15 min). Combined with normal
traffic, this starves the pool for live requests.

## Resolution
1. Confirm via `pg_stat_activity` that the batch job's connections are the
   majority of active connections during the incident window.
2. Restart pgbouncer to force-drop stale/idle connections if the pool is stuck
   saturated after the batch job finishes.
3. Move the reconciliation job to a dedicated connection pool (`batch-pg`)
   separate from live traffic.

## Prevention
- Give batch/cron jobs their own bounded connection pool.
- Add an alert on pool utilization > 90% for > 60s.
