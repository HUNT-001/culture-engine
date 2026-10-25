"""Run the offline CommonThreadBench v2 evaluation and write results + report.

    python -m bench.run_benchmark

Offline by construction: outbound sockets are blocked for the whole process, the Qloo
service is replaced by an in-process mock transport, and the application database is a
throwaway SQLite file. Re-running on unchanged code reproduces identical output.

Writes:
  * bench/results/benchmark_results.json   (full machine-readable results)
  * docs/COMMON_THREAD_BENCHMARK_RESULTS.md (rendered report)
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from bench import testing

BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = BACKEND_DIR.parent
RESULTS_JSON = BACKEND_DIR / "bench" / "results" / "benchmark_results.json"
REPORT_MD = REPO_ROOT / "docs" / "COMMON_THREAD_BENCHMARK_RESULTS.md"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json-only", action="store_true")
    ap.add_argument("--skip-guard", action="store_true",
                    help="skip the stale-base guard (not recommended)")
    args = ap.parse_args(argv)

    testing.isolate_environment()          # before any app.db import
    testing.block_network_for_process()
    from bench.render import render_markdown  # imports app modules; after isolation
    from bench.report import build_results

    results = build_results(skip_guard=args.skip_guard)
    RESULTS_JSON.parent.mkdir(parents=True, exist_ok=True)
    RESULTS_JSON.write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n",
                            encoding="utf-8")
    print(f"Wrote {RESULTS_JSON.relative_to(REPO_ROOT)}")
    if not args.json_only:
        REPORT_MD.write_text(render_markdown(results), encoding="utf-8")
        print(f"Wrote {REPORT_MD.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
