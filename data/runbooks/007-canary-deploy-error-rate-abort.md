# Runbook: Canary Deployment Aborted on Error Rate Threshold

**Services affected:** gateway
**Error codes:** DEPLOY_FAILED, NULL_POINTER

## Symptoms
- Canary analysis aborts the rollout automatically, citing `http_5xx_ratio`
  above threshold during a partial traffic shift.
- Application logs from the canary pods show an unhandled exception (e.g.
  `AttributeError: 'NoneType' object has no attribute 'headers'`).

## Root Cause
The new version assumes a request field (e.g. `Authorization` header) is
always present, but a subset of real traffic (e.g. health checks, or
requests from an older client) doesn't set it, causing an unhandled
exception that surfaces as a 500.

## Resolution
1. Pull canary pod logs to find the exact stack trace and request pattern
   that triggers it.
2. Add a null/defensive check for the missing field, or fix upstream
   clients that omit it.
3. Re-run the canary at a small traffic percentage before proceeding to
   full rollout.

## Prevention
- Add contract tests against the canary using a sample of real traffic
  shapes (including edge cases like missing optional headers) before
  shifting live traffic.
