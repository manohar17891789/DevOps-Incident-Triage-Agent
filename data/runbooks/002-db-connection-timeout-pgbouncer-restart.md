# Runbook: Connection Pool Stuck Saturated After Traffic Spike

**Services affected:** payments-service
**Error codes:** DB_CONN_TIMEOUT, DB_POOL_SATURATED

## Symptoms
- Repeated `connection to server ... timeout expired` errors.
- Pool utilization warning logged (`active=100/100, idle=0`) but does not
  recover on its own even after traffic subsides.

## Root Cause
A burst of slow queries (missing index, or a lock held by another
transaction) causes connections to be checked out longer than usual.
pgbouncer's connection reuse gets stuck because the underlying TCP
connections to Postgres are in a half-open state after a brief network
blip, so pgbouncer thinks they're busy when they're actually dead.

## Resolution
1. Check `pg_stat_activity` for long-running or idle-in-transaction sessions.
2. If connections appear dead but pgbouncer still counts them as active,
   restart pgbouncer (`systemctl restart pgbouncer` or the equivalent
   Kubernetes pod restart) to clear stale connection state.
3. Verify pool utilization drops back to baseline (< 20%) within a minute
   of restart.

## Prevention
- Enable `server_reset_query` and TCP keepalives in pgbouncer config so
  dead connections are detected and recycled automatically.
