# Runbook: Service-to-Service Auth Failures from Disabled Token Refresh Job

**Services affected:** auth-service, gateway
**Error codes:** TOKEN_EXPIRED, REFRESH_CRON_MISSING

## Symptoms
- Sudden spike in `jwt.ExpiredSignatureError` / 401s across many
  service-to-service calls at roughly the same time.
- Gateway logs show it's using a cached token that hasn't refreshed in
  much longer than the expected interval (e.g. 26h vs. expected 1h).

## Root Cause
The cronjob responsible for refreshing the shared service-to-service token
(`token-refresher`) silently stopped running — often after a config sync or
cluster maintenance that disabled or unscheduled it — so the last-issued
token eventually expired and nothing replaced it.

## Resolution
1. Check the cronjob's last successful run timestamp
   (`kubectl get cronjob token-refresher`).
2. Re-enable/trigger the cronjob manually to issue a fresh token
   immediately.
3. Confirm downstream 401 rate drops back to baseline within a few minutes
   of the new token propagating.

## Prevention
- Alert if `token-refresher` has not had a successful run within
  1.5x its expected interval.
- Make token expiry itself trigger an automatic refresh (self-healing)
  rather than depending solely on a cron schedule.
