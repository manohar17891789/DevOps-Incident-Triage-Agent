# Runbook: Notification Worker Memory Leak in Email Template Cache

**Services affected:** notification-worker
**Error codes:** HIGH_MEM_USAGE, OOM_KILLED

## Symptoms
- Worker RSS grows linearly (~100-150MB/hour) starting right after a deploy.
- Eventually OOMKilled; restarting temporarily resolves it but the leak
  recurs at the same rate.

## Root Cause
The email template renderer caches rendered templates keyed by
`(template_id, user_locale, campaign_id)` in a plain Python dict that is
never evicted. Because `campaign_id` is high-cardinality, the cache grows
without bound as new campaigns run.

## Resolution
1. Identify the leaking structure via `tracemalloc` snapshots taken an hour
   apart.
2. Bound the cache (e.g. `functools.lru_cache(maxsize=500)` or an explicit
   TTL cache) keyed only on `(template_id, user_locale)` — drop
   `campaign_id` from the cache key since template content doesn't vary by
   campaign.
3. Deploy the fix and confirm RSS plateaus instead of growing.

## Prevention
- Any per-request or per-message cache must have a bounded key space or
  explicit size/TTL limits before merge.
