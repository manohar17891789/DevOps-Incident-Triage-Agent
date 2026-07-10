# Runbook: OOMKill from Unbounded In-Memory Cache

**Services affected:** recommendation-engine
**Error codes:** HIGH_MEM_USAGE, OOM_KILLED

## Symptoms
- Container memory usage climbs steadily from deploy time, crossing 80%
  within hours and eventually triggering an OOMKill.
- Repeated OOMKills / restart-count increases over successive days after a
  specific release.
- Heap dump shows a single large dict/cache object dominating retained
  memory.

## Root Cause
`v2.9.0` introduced an `LRUCache` used for memoizing recommendation scores
without a `max_size` bound. Under production traffic the cache grows
unbounded until the container hits its memory limit and is killed by the
kubelet's OOMKiller.

## Resolution
1. Confirm via heap dump / memory profiler that the cache object is the
   largest retained structure.
2. Roll back to the pre-v2.9.0 image as an immediate mitigation, or hot-patch
   with an environment variable that caps cache size.
3. Ship a fix that sets an explicit `max_size` and TTL eviction policy on
   the cache.

## Prevention
- Code review checklist item: any new in-memory cache must specify a bound.
- Add a memory-growth-rate alert (not just absolute usage) to catch leaks
  earlier, before they reach OOMKill.
