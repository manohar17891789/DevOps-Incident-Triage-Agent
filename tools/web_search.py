"""Stub web search: returns canned 'known issue' results by keyword category.

Placeholder for a real search API (e.g. Tavily, Serper, Bing). Kept as a
separate module so swapping in a real HTTP call later only touches this
file, not the agent or its tests.
"""
from tools.schemas import WebSearchInput, WebSearchOutput, WebSearchResult

_KNOWN_ISSUES: dict[str, list[WebSearchResult]] = {
    "connection pool": [
        WebSearchResult(
            title="pgbouncer: connections stuck 'active' after network blip",
            url="https://github.com/pgbouncer/pgbouncer/issues/482",
            snippet="Half-open TCP connections after a brief network partition can leave "
            "pgbouncer reporting connections as active when the backend is dead. "
            "Fix: enable tcp_keepalive and server_reset_query.",
        ),
        WebSearchResult(
            title="Postgres connection pool exhaustion under batch + live traffic",
            url="https://www.postgresql.org/message-id/flat/batch-pool-exhaustion",
            snippet="Long-running batch jobs sharing a pool with live traffic is a common "
            "cause of pool exhaustion; recommend a dedicated pool per workload class.",
        ),
    ],
    "oom": [
        WebSearchResult(
            title="Kubernetes OOMKilled: diagnosing unbounded in-process caches",
            url="https://kubernetes.io/docs/tasks/debug/debug-application/troubleshoot-oomkilled",
            snippet="Most OOMKilled incidents in long-running services trace back to an "
            "unbounded cache or growing collection with no eviction policy.",
        ),
    ],
    "memory leak": [
        WebSearchResult(
            title="Python memory leak in dict-based cache without eviction",
            url="https://docs.python.org/3/library/functools.html#functools.lru_cache",
            snippet="Unbounded dict caches keyed on high-cardinality fields are a frequent "
            "source of slow memory growth; bound with lru_cache(maxsize=...) or a TTL cache.",
        ),
    ],
    "deploy failed": [
        WebSearchResult(
            title="Kubernetes rollout stuck: readiness probe failing after config change",
            url="https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-startup-probes/",
            snippet="A frequent cause of new-version readiness failures is a required "
            "config key that wasn't added to the ConfigMap/Secret alongside the code change.",
        ),
    ],
    "migration": [
        WebSearchResult(
            title="Postgres: avoid long lock waits on ADD COLUMN / CREATE INDEX for large tables",
            url="https://www.postgresql.org/docs/current/sql-createindex.html#SQL-CREATEINDEX-CONCURRENTLY",
            snippet="Use CREATE INDEX CONCURRENTLY and default-less column additions with a "
            "batched backfill to avoid lock timeouts on large tables.",
        ),
    ],
    "token expired": [
        WebSearchResult(
            title="JWT ExpiredSignatureError spike after cronjob silently disabled",
            url="https://stackoverflow.com/questions/jwt-expired-after-cron-disabled",
            snippet="Service-to-service token refresh cronjobs that silently stop running "
            "are a common root cause of correlated 401 spikes across many callers at once.",
        ),
    ],
    "signature": [
        WebSearchResult(
            title="JWT InvalidSignatureError after key rotation: JWKS caching",
            url="https://auth0.com/docs/get-started/applications/signing-keys/rotate-signing-keys",
            snippet="Verifiers caching JWKS responses past the key rotation overlap window "
            "will reject tokens signed with the newly rotated key.",
        ),
    ],
    "rate limit": [
        WebSearchResult(
            title="API client retry storms: why backoff-less retries amplify 429s",
            url="https://cloud.google.com/storage/docs/retry-strategy",
            snippet="Clients that retry 429/5xx immediately without exponential backoff can "
            "turn a minor rate-limit event into a cascading overload of downstream services.",
        ),
    ],
}


def run_web_search(input: WebSearchInput) -> WebSearchOutput:
    query = input.query.lower()
    matches: list[WebSearchResult] = []
    for category, results in _KNOWN_ISSUES.items():
        if category in query:
            matches.extend(results)

    if not matches:
        return WebSearchOutput(
            success=True,
            results=[
                WebSearchResult(
                    title="No known public issues found",
                    url="",
                    snippet="No matching known-issue entries for this query in the mock index.",
                )
            ],
        )

    return WebSearchOutput(success=True, results=matches)
