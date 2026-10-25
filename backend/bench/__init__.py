"""CommonThreadBench v2 — production-linked offline evaluation for Common Thread.

v2 replaces the v1 harness, which was built against a stale application revision and
measured mostly its own synthetic fixtures. v2 drives the *real* application code
(QlooClient parsing, resolution policy, workflow, ranking, evidence mapping, API routes)
with Qloo-shaped HTTP fixtures served from an in-process ``httpx.MockTransport``.

This package is evaluation-only. It never changes production ranking, resolution,
frontend behaviour or configuration, and it must not be imported by ``app.*``.
See ``docs/COMMON_THREAD_BENCHMARK.md``.
"""

BENCH_VERSION = "2.0"
