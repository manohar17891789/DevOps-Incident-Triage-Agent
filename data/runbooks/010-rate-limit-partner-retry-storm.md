# Runbook: Downstream Rate-Limit Cascade from Partner Retry Storm

**Services affected:** checkout-api, inventory-service
**Error codes:** RATE_LIMIT_EXCEEDED, RETRY_STORM

## Symptoms
- Sharp spike in 429 responses tied to a single `client_id`, far above its
  configured limit.
- The offending client's requests-per-minute keeps climbing even after
  being throttled, rather than backing off.
- Downstream services (e.g. inventory-service) start getting rate-limited
  too, because checkout-api's own retries against them amplify the load.

## Root Cause
A partner integration's client has no exponential backoff on 429/5xx
responses; it retries immediately, multiplying its effective request rate
and cascading load into downstream dependencies.

## Resolution
1. Identify the offending `client_id` and confirm the retry-without-backoff
   pattern in request timing.
2. Apply a temporary, more generous rate limit override for that client
   while they fix their retry logic, or block/throttle harder if the impact
   is severe enough to affect other tenants.
3. Notify the partner team to add exponential backoff with jitter.

## Prevention
- Enforce backoff-aware client libraries/SDKs for partner integrations.
- Add per-client circuit breakers so one noisy client can't cascade load
  into shared downstream services.
