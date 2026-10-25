"""Render v2 results as Markdown. Deterministic: no timestamps or machine paths."""
from __future__ import annotations

from typing import Any


def _r(rate: dict | None) -> str:
    if not rate:
        return "n/a"
    v = rate["value"]
    pct = "n/a" if v is None else f"{v * 100:.1f}%"
    return f"{rate['numerator']}/{rate['denominator']} ({pct})"


def _f(x: Any, nd: int = 3) -> str:
    if x is None:
        return "n/a"
    return f"{x:.{nd}f}" if isinstance(x, float) else str(x)


def render_markdown(res: dict) -> str:
    L: list[str] = []
    w = L.append
    w("# CommonThreadBench v2 — Results (offline, production-linked)")
    w("")
    w(f"*Benchmark version* `{res['bench_version']}` · *required application checkpoint* "
      f"`{res['required_checkpoint']}` · regenerate with `python -m bench.run_benchmark`.")
    w("")
    w("> **Read this first.** Every number below carries a provenance tag. No number comes from "
      "a live request or a human study. Fixtures are synthetic; \"mocked-integration\" means the "
      "real adapter, workflow and routes ran against Qloo-shaped mock HTTP, **not** the real "
      "Qloo service. v1 figures (9.3%, 55.6%, 50%, 100%) were measured against a stale "
      "revision and mostly against the benchmark's own fixtures; they are historical and are "
      "**not** reproduced here (see `docs/benchmark-history/`).")
    w("")
    w("| Tag | Meaning |")
    w("|---|---|")
    for k, v in res["provenance_legend"].items():
        w(f"| `{k}` | {v} |")
    w("")
    g = res["baseline_guard"]
    if g:
        a = g["ancestry"]
        w("## 0. Baseline guard")
        w("")
        w("- HEAD descends from the required checkpoint: "
          f"**{a.get('head_descends_from_checkpoint')}**")
        ok_routes = sum(g["features"]["routes_registered"].values())
        ok_syms = sum(g["features"]["symbols"].values())
        w(f"- Production routes registered (from the live app's OpenAPI): "
          f"{ok_routes}/{len(g['features']['routes_registered'])}")
        w(f"- Production features present: {ok_syms}/{len(g['features']['symbols'])}")
        w("")
    d = res["dataset"]
    w(f"Dataset: {d['n_scenarios']} scenarios, {d['development']} development / "
      f"{d['held_out']} held-out. {d['held_out_policy'][0].upper()}{d['held_out_policy'][1:]}.")
    w("")

    # ------------------------------------------------------------------ ER
    er = res["entity_resolution"]
    w("## 1. Entity resolution — `mocked-integration`")
    w("")
    w(f"Real `QlooClient` + real `resolve_entities` over mock `/search`. Gold: "
      f"*{er['gold_review_status']}*. **n = {er['n_cases']}**, so these rates are indicative "
      "only.")
    w("")
    w("| Subset | False automatic confirmation | Auto-confirm precision | Abstain rate | "
      "Unacceptable outcomes |")
    w("|---|---|---|---|---|")
    for name, key in (("All", "overall"), ("Development", "development"),
                      ("Held-out", "held_out"), ("Exact-name homonyms", "exact_homonym_subset")):
        s = er[key]
        w(f"| {name} | {_r(s['false_auto_confirmation'])} | {_r(s['auto_confirmation_precision'])}"
          f" | {_r(s['abstain_rate'])} | {_r(s['unacceptable_outcome_rate'])} |")
    w("")
    w("| Case | Kind | Outcome | Acceptable |")
    w("|---|---|---|---|")
    for c in er["cases"]:
        ok = "yes" if c["acceptable"] else "**NO**"
        w(f"| `{c['case_id']}` | {c['kind']} | {c['outcome']} | {ok} |")
    w("")
    cp = er["confirmed_path"]
    w(f"- User-confirmed overlay bypasses search: **{cp['never_searched']}**; "
      f"resolves to the intended entity: **{cp['all_correct']}** (n={cp['n']}).")
    w(f"- Gold entity id/type/disambiguation survive adapter + `/api/entities/search` unchanged: "
      f"**{er['candidate_fidelity']['all_ok']}**.")
    cl = er["candidate_list_metrics"]
    w(f"- `synthetic-arithmetic` — Recall@5 = {_f(cl['recall_at_5'])}, MRR = {_f(cl['mrr'])} "
      f"over {cl['n']} author-written candidate lists. {cl['note']}")
    w("")

    # ---------------------------------------------------------- constraints
    c = res["constraints"]
    w("## 2. Constraints — `mocked-integration`")
    w("")
    w("Only constraints production can enforce are scored. v1's violation rate used price and "
      "tag attributes the benchmark invented; v2 does not.")
    w("")
    w("| Probe (through the real workflow) | Development | Held-out | All |")
    w("|---|---|---|---|")
    for label, key in (
        ("Exact-name dislike excludes the venue", "exact_name_enforcement"),
        ("Case-variant exact-name dislike excludes it", "case_variant_enforcement"),
        ("Exclusion is disclosed to the user", "exact_name_exclusion_disclosed"),
        ("All pooled venues disliked → empty, disclosed", "empty_feasible_handled"),
        ("Substring dislike excludes it (not supported)", "substring_dislike_enforcement"),
        ("Category dislike excludes it (not supported)", "category_dislike_enforcement"),
    ):
        w(f"| {label} | {_r(c['development'][key])} | {_r(c['held_out'][key])} | "
          f"{_r(c['overall'][key])} |")
    w("")
    b = c["budget"]
    w(f"- **Budget is not enforced** (`Candidate` has a price field: "
      f"{b['candidate_has_price_field']}). Disclosed as \"not checked\" when a budget is given: "
      f"{_r(b['disclosure_when_budget_given'])}; spuriously disclosed when none is given: "
      f"{_r(b['false_disclosure_when_no_budget'])}. No violation rate is computed.")
    p = c["declared_constraint_prevalence"]
    w(f"- Constraints declared across the 48 scenario files: {p['total']} "
      f"({p['declared']}); enforceable by production: **{p['enforceable_by_production']}**, "
      f"unsupported: **{p['unsupported']}**.")
    w("")

    # ------------------------------------------------------------- evidence
    e = res["evidence"]
    w("## 3. Evidence faithfulness — `mocked-integration`")
    w("")
    w(f"_{e['note']}_")
    w("")
    w("| Claim type | Supported by fixture |")
    w("|---|---|")
    sup = e["overall"]["support"]
    for t, rate in sup["by_type"].items():
        w(f"| {t} | {_r(rate)} |")
    w(f"| **all displayed claims** | **{_r(sup['overall'])}** |")
    w("")
    w(f"- Identifier leaks into user-visible text: **{e['overall']['identifier_leaks']}**.")
    w(f"- Mapping completeness (fixture-credited interests that production displays): "
      f"**{_r(e['overall']['mapping_completeness'])}** — see gap G1.")
    dm = e["demo_mode"]
    w(f"- Mock mode (`production-function`): all labelled synthetic = "
      f"**{dm['all_labelled_synthetic']}**, no Qloo-sourced interests = "
      f"**{dm['no_named_interests']}**, no affinity = **{dm['no_affinity']}**.")
    w("")

    # -------------------------------------------------------------- ranking
    rk = res["ranking"]
    w("## 4. Ranking ablation (Experiment B) and end-to-end (Experiment A)")
    w("")
    w(f"Pool = what the real workflow retrieved through the real adapter. "
      f"{rk['n_scenarios_evaluated']} scenarios evaluated, {rk['n_scenarios_excluded']} "
      f"excluded ({rk['excluded_reason']}). Re-running the production ranker on the pool "
      f"reproduces the workflow's own order in {_r(rk['production_rerun_reproduces_workflow'])}.")
    w("")
    w("Fairness here is computed from each participant's own retrieval list, independent of "
      "every ranker's score. `rank_aggregation` optimises something close to *worst-member "
      "best rank*, so that column favours it by construction. These are structural measures, "
      "**not** quality.")
    w("")
    for split in ("development", "held_out", "all"):
        w(f"**{split}**")
        w("")
        w("| Ranker | Provenance | Mean coverage | All servable served | Served within own top-5 | "
          "Worst-member best rank (↓) | Top-3 Jaccard vs production |")
        w("|---|---|---|---|---|---|---|")
        for m, v in rk["ablation"][split].items():
            prov = ("production-function" if m in rk["production_methods"]
                    else "synthetic-arithmetic")
            w(f"| `{m}` | {prov} | {_f(v['mean_coverage_fraction'])} | {_r(v['all_served'])} | "
              f"{_r(v['all_served_top5'])} | {_f(v['mean_worst_member_best_rank'])} | "
              f"{_f(v['mean_jaccard_vs_production'])} |")
        w("")
    w("**Experiment A (all)** — process metrics only")
    w("")
    w("| Method | Executed | Mean coverage | All servable served | Worst-member best rank (↓) |")
    w("|---|---|---|---|---|")
    for m, v in rk["experiment_a"]["all"].items():
        if not v["executed"]:
            w(f"| `{m}` | **PENDING** | n/a | n/a | n/a |")
        else:
            w(f"| `{m}` | yes | {_f(v['mean_coverage_fraction'])} | {_r(v['all_served'])} | "
              f"{_f(v['mean_worst_member_best_rank'])} |")
    w("")
    w("> The LLM-only baseline is **pending**: the adapter exists but no provider is configured "
      "and none was added. Whether any method yields recommendations people prefer is the human "
      "study's question.")
    w("")

    # --------------------------------------------------------------- faults
    f = res["faults"]
    w("## 5. Fault resilience — `mocked-integration`, end to end")
    w("")
    w(f"{f['level']}. Expectations come from `docs/API_CONTRACTS.md`. "
      f"**{f['meets_contract']}/{f['n_rows']}** rows meet the contract; "
      f"raw-body/secret/stack-trace leaks: **{f['leaks']}**.")
    w("")
    w("| Route | Stage | Fault | Call | Expected | Observed | Code | Requests |")
    w("|---|---|---|---|---|---|---|---|")
    for x in f["rows"]:
        w(f"| {x['route']} | {x['stage']} | {x['kind']} | {x['nth'] or 'all'} | {x['expect']} | "
          f"{x['observed']} | {x['error_code'] or '-'} | {x['qloo_requests']} |")
    w("")
    for k, v in f["coverage_map"].items():
        w(f"- **{k.replace('_', ' ')}** — {v}")
    w("")

    # ----------------------------------------------------------- live/human
    lv = res["live"]
    w("## 6. Live Qloo — `live-request`")
    w("")
    w(f"**Requests made in v2: {lv['requests_made_in_v2']}.** {lv['status']}")
    w("")
    pl = lv["planned_budget_for_next_slice"]
    w(f"Budget a subsequent, separately authorised validation would need "
      f"(**upper bound {pl['total_upper_bound']}**):")
    w("")
    w("| Phase | Requests |")
    w("|---|---|")
    for ph in pl["phases"]:
        w(f"| {ph['phase']} | {ph['requests']} |")
    w("")
    w(f"{pl['bounds']}")
    w("")
    he = res["human_evaluation"]
    w("## 7. Human evaluation — `human-study`")
    w("")
    w(f"**Status: {he['status']}.** {he['note']}")
    w("")
    return "\n".join(L) + "\n"
