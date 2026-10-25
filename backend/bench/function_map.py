"""Measure which production functions each benchmark test file actually executes.

For every ``tests/test_bench_*.py`` file this runs pytest under ``coverage`` (restricted to
``app/``), then maps executed lines onto production function bodies using ``ast``. A function
counts as exercised only if a line of its *own* body ran (nested function bodies are
attributed to the nested function, not the outer one). Import-time execution therefore does
not count.

    python -m bench.function_map                 # all files, writes the markdown map
    python -m bench.function_map --files tests/test_bench_ranking.py

This is a measurement, not prose: it is how the report knows ``test_bench_metrics.py``
exercises no production function at all.
"""
from __future__ import annotations

import argparse
import ast
import json
import subprocess
import sys
import tempfile
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
REPO = BACKEND.parent
NOTE = (
    "`test_bench_metrics` and `test_bench_human_eval` verify metric arithmetic and the "
    "human-study protocol, which says nothing about the product. `test_bench_baseline_guard` "
    "inspects route registration and symbol presence on the live app object without running "
    "the pipeline."
)
OUT_MD = REPO / "docs" / "COMMON_THREAD_BENCHMARK_FUNCTION_MAP.md"

# (file under app/, qualified function name) -- the production behaviour the benchmark claims.
TARGETS = [
    ("providers/qloo.py", "QlooClient._get_json"),
    ("providers/qloo.py", "QlooClient._result_list"),
    ("providers/qloo.py", "QlooClient._entity_subtype"),
    ("providers/qloo.py", "QlooClient._extract_explanation"),
    ("providers/qloo.py", "QlooClient.search_entities"),
    ("providers/qloo.py", "QlooClient.get_place_recommendations"),
    ("services/resolution.py", "exact_match"),
    ("services/resolution.py", "confirmed_index"),
    ("services/resolution.py", "normalize_name"),
    ("workflows/nodes.py", "build_nodes.resolve_entities"),
    ("workflows/nodes.py", "build_nodes.retrieve_insights"),
    ("workflows/nodes.py", "build_nodes.normalize_candidates"),
    ("workflows/nodes.py", "build_nodes.rank_options"),
    ("workflows/nodes.py", "build_nodes.validate_evidence"),
    ("workflows/nodes.py", "build_nodes.compose_response"),
    ("workflows/nodes.py", "build_nodes.validate_output"),
    ("services/ranking.py", "merge_candidate_batches"),
    ("services/ranking.py", "apply_hard_constraints"),
    ("services/ranking.py", "rank_candidates"),
    ("services/ranking.py", "select_options"),
    ("services/ranking.py", "_affinity_of"),
    ("services/ranking.py", "_affinity_bounds"),
    ("services/evidence.py", "build_interest_index"),
    ("services/evidence.py", "matched_interest_names"),
    ("services/provenance.py", "validate_and_label_options"),
    ("providers/composer.py", "DeterministicComposer.compose"),
    ("providers/mock_qloo.py", "MockQlooClient.get_place_recommendations"),
    ("api/routes/recommendations.py", "execute_workflow"),
    ("api/routes/entities.py", "search_entities"),
    ("api/routes/plans.py", "run_plan_recommendations"),
    ("api/routes/plans.py", "create_plan"),
    ("domain/schemas.py", "RecommendationRequest.check_unique_participants"),
]


def _function_bodies(path: Path) -> dict[str, set[int]]:
    """qualname -> the set of line numbers that belong to that function's own body."""
    tree = ast.parse(path.read_text())
    out: dict[str, set[int]] = {}

    def visit(node, prefix: str):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                qn = f"{prefix}{child.name}"
                body = child.body
                # skip a leading docstring
                if (body and isinstance(body[0], ast.Expr)
                        and isinstance(getattr(body[0], "value", None), ast.Constant)
                        and isinstance(body[0].value.value, str)):
                    body = body[1:]
                lines: set[int] = set()
                for stmt in body:
                    lines.update(range(stmt.lineno, (stmt.end_lineno or stmt.lineno) + 1))
                nested: set[int] = set()
                for n in ast.walk(child):
                    if n is not child and isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        nested.update(range(n.lineno, (n.end_lineno or n.lineno) + 1))
                out[qn] = lines - nested
                visit(child, qn + ".")
            elif isinstance(child, ast.ClassDef):
                visit(child, f"{prefix}{child.name}.")
            else:
                visit(child, prefix)

    visit(tree, "")
    return out


def _executed(test_file: str, tmp: Path) -> dict[str, set[int]]:
    data = tmp / f".cov_{Path(test_file).stem}"
    env_cmd = [sys.executable, "-m", "coverage", "run", f"--data-file={data}", "--source=app",
               "-m", "pytest", test_file, "-q", "-p", "no:cacheprovider", "-x", "--no-header"]
    proc = subprocess.run(env_cmd, cwd=BACKEND, capture_output=True, text=True)
    if proc.returncode not in (0,):
        raise SystemExit(f"{test_file} failed under coverage:\n{proc.stdout[-1500:]}")
    js = tmp / f"{data.name}.json"
    subprocess.run([sys.executable, "-m", "coverage", "json", f"--data-file={data}", "-o", str(js)],
                   cwd=BACKEND, check=True, capture_output=True, text=True)
    report = json.loads(js.read_text())
    return {Path(f).as_posix(): set(v["executed_lines"]) for f, v in report["files"].items()}


def build_map(test_files: list[str]) -> dict:
    app_dir = BACKEND / "app"
    bodies = {rel: _function_bodies(app_dir / rel) for rel in {t[0] for t in TARGETS}}
    matrix: dict[str, dict[str, bool]] = {}
    with tempfile.TemporaryDirectory() as td:
        for tf in test_files:
            executed = _executed(tf, Path(td))
            row = {}
            for rel, qn in TARGETS:
                key = next((f for f in executed if f.endswith("app/" + rel)), None)
                own = bodies[rel].get(qn)
                if own is None:
                    raise SystemExit(f"target not found: {rel}:{qn}")
                row[f"{rel}:{qn}"] = bool(key and own & executed[key])
            matrix[tf] = row
    return matrix


def render(matrix: dict) -> str:
    files = list(matrix)
    short = [Path(f).stem.replace("test_bench_", "") for f in files]
    L = ["# CommonThreadBench v2 — Production functions exercised, per test file", "",
         "Measured, not asserted: each `tests/test_bench_*.py` file was run under `coverage` "
         "and executed lines were mapped onto production function bodies "
         "(`python -m bench.function_map`). ✓ = a line of the function's own body ran. "
         "Import-time execution does not count.", "",
         "| Production function | " + " | ".join(short) + " |",
         "|---|" + "---|" * len(files)]
    for rel, qn in TARGETS:
        key = f"{rel}:{qn}"
        cells = " | ".join("✓" if matrix[f][key] else "·" for f in files)
        L.append(f"| `{rel}` · `{qn}` | {cells} |")
    L.append("")
    L.append("**Test files that execute none of the listed behavioural functions:** "
             + (", ".join(f"`{Path(f).name}`" for f in files if not any(matrix[f].values()))
                or "none") + ". " + NOTE)
    L.append("")
    never = [f"{rel}:{qn}" for rel, qn in TARGETS
             if not any(matrix[f][f"{rel}:{qn}"] for f in files)]
    L.append("**Listed production functions never executed by any benchmark test:** "
             + (", ".join(f"`{n}`" for n in never) or "none") + ".")
    return "\n".join(L) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--files", nargs="*")
    args = ap.parse_args(argv)
    files = args.files or sorted(str(p.relative_to(BACKEND))
                                 for p in (BACKEND / "tests").glob("test_bench_*.py"))
    matrix = build_map(files)
    md = render(matrix)
    if not args.files:
        OUT_MD.write_text(md, encoding="utf-8")
        print(f"Wrote {OUT_MD.relative_to(REPO)}")
    print(md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
