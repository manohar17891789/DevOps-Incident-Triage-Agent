# Runbook: Deploy Failure from Missing ConfigMap Key

**Services affected:** user-service
**Error codes:** DEPLOY_FAILED, CONFIG_MISSING

## Symptoms
- Rollout fails readiness probes on all replicas of the new version.
- Application logs show a `KeyError` or similar on startup, referencing an
  environment variable that should come from a ConfigMap/Secret.
- Deploy pipeline auto-rollback kicks in after repeated failed health checks.

## Root Cause
The new release added a required config key (e.g. `USER_DB_SECRET_KEY`)
to the application's settings loader, but the corresponding ConfigMap/Secret
manifest was not updated in the same change, so the new pods crash on
startup while old pods (still running the old config schema) are fine.

## Resolution
1. Check the failing pod's logs for the exact missing key.
2. Add the missing key to the ConfigMap/Secret for the target environment.
3. Re-trigger the rollout; confirm readiness probes pass.

## Prevention
- Treat config schema changes and the code that requires them as a single
  atomic deploy unit; add a pre-deploy check that diffs required env vars
  against the target ConfigMap.
- Make new config keys optional with sane defaults for at least one release
  before making them required.
