# Runbook: 401 Spike from Signing Key Rotation Mismatch

**Services affected:** auth-service, gateway
**Error codes:** TOKEN_EXPIRED (misleading), JWT signature errors

## Symptoms
- Spike in 401s for internal service calls shortly after a certificate /
  signing-key rotation.
- Error is `InvalidSignatureError` rather than `ExpiredSignatureError` —
  the token isn't expired, its signature just doesn't validate.

## Root Cause
`auth-service` rotated its JWT signing key, but `gateway` (and possibly
other verifiers) cache the public key / JWKS response for longer than the
rotation overlap window. Tokens issued with the new key fail verification
against the stale cached key.

## Resolution
1. Confirm the error is a signature mismatch, not expiry, by checking the
   exception type in logs.
2. Force an immediate JWKS cache refresh on affected services (restart or
   invalidate the cache).
3. Confirm 401 rate returns to baseline.

## Prevention
- Keep both old and new signing keys valid in the JWKS endpoint for an
  overlap period at least as long as the longest verifier's cache TTL.
- Reduce JWKS cache TTL, or add a "kid not found -> force refresh" fallback
  in verifiers so rotation doesn't require manual intervention.
