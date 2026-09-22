"""
probes/findings.py
==================
Every figure quoted in docs/FINDINGS.md, recomputed from committed data.

FINDINGS.md is the standalone write-up, aimed at a reader who has never
seen this repo and will check its claims against the code. That reader
needs a command, not a citation to a previous session — and the standing
rule in CLAUDE.md section 9 says every number in a report must come from
something run in the session that reports it. This is that something.

Each report below corresponds to a numbered footnote in FINDINGS.md.
Run one, or run them all:

    python probes/findings.py               # every report, in doc order
    python probes/findings.py humaneval     # [1] the founding case
    python probes/findings.py coverage      # [2] what is and is not measured
    python probes/findings.py backtest      # [3] the retirement test, pairwise
    python probes/findings.py candidate1    # [4] the second pre-registered test
    python probes/findings.py noise         # [5] scatter, and HEALTHY_SPREAD
    python probes/findings.py cliff         # [6] the population threshold
    python probes/findings.py modelside     # [7] citations, tiers, repeats
    python probes/findings.py correlations  # [8] what predicts the retirement

Touches no network; everything comes from data/.
"""

from __future__ import annotations

import collections
import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

MODELS_PATH = ROOT / "data" / "models_raw.json"


def humaneval() -> None:
    """[1] The founding case, stated as evidence about one benchmark."""
    from benchmark_scoring import score_all_benchmarks
    from fetch_benchmarks import load_benchmark_scores

    print("\n[1] HUMANEVAL — the founding case\n")
    trust = next(t for t in score_all_benchmarks() if t.benchmark.name == "HumanEval")
    b = trust.benchmark
    scores = load_benchmark_scores(b)
    print(f"  released            {b.release_date}")
    print(f"  health              {trust.health:.1f}  (tier: {trust.evidence_tier})")
    print(f"  evidence            {trust.evidence_summary}")
    for f in trust.factors:
        value = "n/a" if f.value is None else f"{f.value:.3f}"
        print(f"    {f.name:16} {value:>7}  basis={f.basis}  weight={f.weight:.2f}")
    print(f"  population          {scores.population} (n={len(scores.scores)})")
    print(f"  contamination rate  {b.contamination_rate}")
    print(
        f"  contamination eff.  {b.contamination_effect} "
        f"(basis: {b.contamination_effect_basis})"
    )
    print(
        f"  item error rate     {b.item_error_rate} "
        f"(basis: {b.item_error_rate_basis}) "
        f"-- None means nobody audited it"
    )
    for p in trust.penalties:
        print(f"  penalty             {p}")


def coverage() -> None:
    """[2] What the catalog has actually measured, and for how many."""
    from benchmark_scoring import measure_saturation
    from cross_source import agreement_for
    from fetch_benchmarks import (
        find_benchmark as find_benchmark_by_name,
        load_benchmark_catalog,
        load_benchmark_scores,
    )

    catalog = load_benchmark_catalog()
    print(f"\n[2] COVERAGE — catalog of {len(catalog)} benchmarks\n")

    sourced = saturated = 0
    populations: collections.Counter = collections.Counter()
    for b in catalog:
        scores = load_benchmark_scores(b)
        if scores is None or not scores.scores:
            continue
        sourced += 1
        populations[scores.population] += 1
        if measure_saturation(scores)[0] is not None:
            saturated += 1
    agreed = sum(1 for b in catalog if agreement_for(b) is not None)

    print(f"  has any score source          {sourced:>3} of {len(catalog)}")
    print(f"  saturation measured           {saturated:>3} of {len(catalog)}")
    print(f"  cross-source agreement        {agreed:>3} of {len(catalog)}")
    print(
        f"  contamination rate known      "
        f"{sum(1 for b in catalog if b.contamination_rate is not None):>3} of {len(catalog)}"
    )
    print(
        f"  contamination effect known    "
        f"{sum(1 for b in catalog if b.contamination_effect is not None):>3} of {len(catalog)}"
    )
    print(
        f"  contamination merely flagged  "
        f"{sum(1 for b in catalog if b.contamination_flagged):>3} of {len(catalog)}"
    )
    print(
        f"  item error rate known         "
        f"{sum(1 for b in catalog if b.item_error_rate is not None):>3} of {len(catalog)}"
    )
    print(
        f"  specificity rubric scored     "
        f"{sum(1 for b in catalog if b.specificity_dimensions):>3} of {len(catalog)}"
        "   (all by Claude Code; see CLAUDE.md section 3)"
    )
    print("\n  populations the readings come from -- readings do NOT compare across these:")
    for name, n in populations.most_common():
        print(f"    {n:>3}  {name}")

    # The same benchmark, read on two populations. This is the clearest
    # case that a saturation number describes a (benchmark, population)
    # pair and not a benchmark.
    from cross_source import load_score_sets

    print("\n  GPQA Diamond, the same benchmark read on two populations:")
    for scores in load_score_sets(find_benchmark_by_name("GPQA Diamond")):
        value = measure_saturation(scores)[0]
        shown = "n/a" if value is None else f"{value:.3f}"
        print(f"    sat={shown}  n={len(scores.scores):>5}  {scores.population}")


def backtest() -> None:
    """[3] The retirement test, scored pairwise, against the calendar."""
    from backtest import CUTOFF, REPLACEMENTS, RETIRED
    from benchmark_scoring import score_benchmark
    from fetch_benchmarks import find_benchmark

    print(f"\n[3] HF RETIREMENT BACKTEST — as of {CUTOFF}\n")
    info = {}
    for name in RETIRED + REPLACEMENTS:
        b = find_benchmark(name)
        t = score_benchmark(b, as_of=CUTOFF)
        info[name] = (t.health, t.evidence_tier, b.release_date)
    for name, (health, tier, date) in sorted(info.items(), key=lambda x: -x[1][0]):
        actual = "RETIRED" if name in RETIRED else "kept"
        print(f"  {name[:30]:31}{health:6.1f}  {tier:8} {date}  {actual}")

    valid = void = scorer = calendar = 0
    void_pairs = []
    for r in RETIRED:
        for k in REPLACEMENTS:
            if info[r][1] != info[k][1]:
                void += 1
                void_pairs.append((r, k))
                continue
            valid += 1
            scorer += info[r][0] < info[k][0]
            calendar += info[r][2] < info[k][2]
    total = len(RETIRED) * len(REPLACEMENTS)
    print(f"\n  pairs {total}: {valid} valid (same tier), {void} void (cross-tier)")
    print(f"    scorer correct         {scorer}/{valid}")
    print(f"    release date correct   {calendar}/{valid}")
    print(f"  every void pair involves {sorted({k for _, k in void_pairs})}")
    print(
        "\n  Both are perfect, so the test cannot separate them. That is a\n"
        "  property of these twelve: HF retired the older six and kept the\n"
        "  newer six, so scorer and calendar agree by construction on every\n"
        "  valid pair. Run `python backtest.py --sweep` for the single-factor\n"
        "  comparison and the release-date baseline."
    )


def candidate1() -> None:
    """[4] The second pre-registered test, re-measured at its own as-of date."""
    from benchmark_scoring import score_all_benchmarks

    as_of = "2026-02-01"  # the date fixed in docs/SECOND_TEST_PREREGISTRATION.md
    print(f"\n[4] CANDIDATE 1 — OpenAI abandons SWE-Bench Verified, as of {as_of}\n")
    ranked = {t.benchmark.name: t for t in score_all_benchmarks(as_of=as_of)}
    swe, gpqa = ranked["SWE-Bench Verified"], ranked["GPQA Diamond"]
    for t in (swe, gpqa):
        print(
            f"  {t.benchmark.name[:24]:25}{t.health:6.1f}  "
            f"{t.evidence_tier:8} {t.evidence_summary}"
        )
    print(f"\n  SWE-Bench Verified - GPQA Diamond = {swe.health - gpqa.health:+.1f}")
    print(
        "  The pre-registration recorded +16.6 under the definitions of the\n"
        "  day. The DIRECTION is unchanged and is still the failure: the\n"
        "  scorer puts the benchmark a frontier lab was about to abandon\n"
        "  ABOVE the older one that stayed in use. The magnitude has moved\n"
        "  with three definition changes since, which is why it is\n"
        "  re-measured here rather than quoted.\n"
        f"  The pair is also VOID under the tiering rule: {swe.evidence_tier}\n"
        f"  against {gpqa.evidence_tier}."
    )


def noise() -> None:
    """[5] The measurable noise floor, and the constant derived from it."""
    from benchmark_scoring import HEALTHY_SPREAD
    from cross_source import SCATTER_TOLERANCE, agreement_for
    from fetch_benchmarks import load_benchmark_catalog

    print("\n[5] CROSS-SOURCE SCATTER — the only noise floor this repo measures\n")
    rows = []
    for b in load_benchmark_catalog():
        a = agreement_for(b)
        if a is not None and a.scatter is not None:
            rows.append((b.name, a.scatter, a.offset, a.overlap))
    for name, scatter, offset, overlap in sorted(rows, key=lambda r: r[1]):
        print(
            f"  {name[:30]:31} scatter={scatter:.4f}  offset={offset:+.4f}  "
            f"models={overlap}"
        )
    scatters = [r[1] for r in rows]
    print(
        f"\n  n={len(scatters)}  median {statistics.median(scatters):.4f}  "
        f"mean {statistics.mean(scatters):.4f}  max {max(scatters):.4f}"
    )
    print(f"  3 x max = {3 * max(scatters):.4f}  ->  HEALTHY_SPREAD = {HEALTHY_SPREAD}")
    print(f"  SCATTER_TOLERANCE (model-side reuse) = {SCATTER_TOLERANCE}")
    print(
        "\n  The multiplier 3 is chosen, not derived, and is named as such in\n"
        "  benchmark_scoring.py. See `python probes/impact.py parameter\n"
        "  HEALTHY_SPREAD 0.084 0.197 0.24 0.358` for what the defensible\n"
        "  range does to the catalog."
    )


def cliff() -> None:
    """[6] The 30-model minimum, and the benchmarks sitting near it."""
    from benchmark_scoring import (
        MIN_SATURATION_POPULATION,
        SATURATION_TOP_PERCENTILE,
        measure_saturation,
    )
    from fetch_benchmarks import load_benchmark_catalog, load_benchmark_scores

    print(
        f"\n[6] POPULATION CLIFF — minimum {MIN_SATURATION_POPULATION}, "
        f"top {SATURATION_TOP_PERCENTILE:.0f}%\n"
    )
    rows = []
    for b in load_benchmark_catalog():
        scores = load_benchmark_scores(b)
        n = 0 if scores is None else len(scores.scores)
        measured = scores is not None and measure_saturation(scores)[0] is not None
        rows.append((b.name, n, measured))
    near = sorted(
        (r for r in rows if 0 < r[1] <= MIN_SATURATION_POPULATION + 15),
        key=lambda r: r[1],
    )
    print("  benchmarks within 15 models of the threshold, either side:")
    for name, n, measured in near:
        side = "measured" if measured else "UNMEASURABLE"
        print(f"    {name[:30]:31} n={n:>3}  {side}")
    print(
        "\n  See docs/POPULATION_CLIFF.md, and\n"
        "  `python probes/impact.py parameter MIN_SATURATION_POPULATION "
        "20 25 30 35 40`\n  for what moving the threshold does."
    )


def modelside() -> None:
    """[7] Model-side citations, weighting, and repeated labels."""
    from benchmark_scoring import score_all_benchmarks
    from enrich_scores import build_external_index
    from fetch_benchmarks import find_benchmark
    from scoring import score_models

    print("\n[7] MODEL SIDE\n")
    if not MODELS_PATH.exists():
        print(f"  (no {MODELS_PATH.name} — run fetch_models.py; skipped)")
        return
    raw = json.loads(MODELS_PATH.read_text())["models"]
    scored = [m for m in score_models(raw, index=build_external_index())
              if m.composite_score is not None]
    citations = sum(len(m.benchmark_breakdown) for m in scored)
    print(f"  scored models {len(scored)}, benchmark citations {citations}")

    ranked = [m for m in scored if m.has_weighted_evidence]
    print(f"    ranked (>=1 weighted citation)       {len(ranked)}")
    print(f"    shown as unweighted evidence only    {len(scored) - len(ranked)}")
    covered = sum(
        1 for m in scored
        if any(find_benchmark(p["benchmark"]) for p in m.benchmark_breakdown)
    )
    print(
        f"    model-weighted coverage              {covered}/{len(scored)} "
        f"({covered / len(scored):.0%}) have >=1 catalogued citation"
    )

    tier_of = {t.benchmark.name: t.evidence_tier for t in score_all_benchmarks()}
    by_tier: collections.Counter = collections.Counter()
    for m in scored:
        for p in m.benchmark_breakdown:
            known = find_benchmark(p["benchmark"])
            by_tier[tier_of.get(known.name) if known else "unrecognised"] += 1
    print("\n  citations by the tier of the benchmark cited:")
    for tier, n in by_tier.most_common():
        print(f"    {str(tier):14}{n:>5}  ({n / citations:.0%})")

    groups = {}
    for m in scored:
        for p in m.benchmark_breakdown:
            if p.get("repeated"):
                groups[(m.model_id, p["benchmark"], p["source"])] = p["repeated"]
    spreads = sorted(g["spread"] for g in groups.values())
    entries = sum(g["entries"] for g in groups.values())
    print(
        f"\n  repeated labels — one source reporting one label more than once\n"
        f"    groups (model, label, source)        {len(groups)}\n"
        f"    models affected                      {len({k[0] for k in groups})}"
        f" of {len(scored)}\n"
        f"    entries inside those groups          {entries} of {citations} citations\n"
        f"    spread  min {spreads[0]:.3f}  median {statistics.median(spreads):.3f}"
        f"  max {spreads[-1]:.3f}\n"
        f"    groups above the 0.08 scatter tolerance  "
        f"{sum(1 for s in spreads if s > 0.08)}\n"
        f"    ranked models affected               "
        f"{sum(1 for m in ranked if m.model_id in {k[0] for k in groups})}"
    )
    worst = max(groups.items(), key=lambda kv: kv[1]["spread"])
    (model_id, label, source), note = worst
    print(f"\n    widest: {model_id} / {label} [{source}]")
    print(f"      {note['entries']} entries, spread {note['spread']:.3f}")
    print(f"      {note['values']}")
    print(
        "      These are pass@1, pass@10, pass@100 and exact_match under one\n"
        "      label. pass@100 exceeds pass@1 by construction, so the mean is\n"
        "      over different quantities, not repeated measurements."
    )


def correlations() -> None:
    """[8] What actually predicts HF's retire/keep decision."""
    import datetime

    from backtest import CUTOFF, REPLACEMENTS, RETIRED
    from benchmark_scoring import measure_saturation, score_benchmark
    from fetch_benchmarks import find_benchmark, load_benchmark_scores

    def pearson(xs, ys):
        mx, my = statistics.mean(xs), statistics.mean(ys)
        num = sum((a - mx) * (b - my) for a, b in zip(xs, ys))
        den = (
            sum((a - mx) ** 2 for a in xs) * sum((b - my) ** 2 for b in ys)
        ) ** 0.5
        return num / den

    print(f"\n[8] WHAT PREDICTS THE RETIREMENT DECISION — as of {CUTOFF}\n")
    cutoff = datetime.date.fromisoformat(CUTOFF)
    age, saturation, kept, health = [], [], [], []
    for name in RETIRED + REPLACEMENTS:
        b = find_benchmark(name)
        age.append((cutoff - datetime.date.fromisoformat(b.release_date)).days)
        scores = load_benchmark_scores(b)
        saturation.append(
            None if scores is None else measure_saturation(scores.before(CUTOFF))[0]
        )
        kept.append(0 if name in RETIRED else 1)
        health.append(score_benchmark(b, as_of=CUTOFF).health)

    sat_pairs = [(s, k) for s, k in zip(saturation, kept) if s is not None]
    age_sat = [(a, s) for a, s in zip(age, saturation) if s is not None]
    print(f"  saturation measurable at the cutoff for {len(sat_pairs)} of 12\n")
    print(
        f"  r(age, kept)                 {pearson(age, kept):+.3f}   "
        "negative = older benchmarks were retired"
    )
    print(f"  r(health, kept)              {pearson(health, kept):+.3f}")
    print(
        f"  r(saturation, kept)          "
        f"{pearson([p[0] for p in sat_pairs], [p[1] for p in sat_pairs]):+.3f}   "
        f"(n={len(sat_pairs)})"
    )
    print(
        f"  r(age, measured saturation)  "
        f"{pearson([p[0] for p in age_sat], [p[1] for p in age_sat]):+.3f}   "
        f"(n={len(age_sat)})"
    )
    print(
        "\n  Age predicts the decision far better than the composite health\n"
        "  score does, and measured saturation -- the factor carrying the\n"
        "  most weight -- barely predicts it at all. Age and saturation are\n"
        "  also only weakly related, so saturation is not standing in for\n"
        "  age; it is adding little on this set either way."
    )


REPORTS = {
    "humaneval": humaneval,
    "coverage": coverage,
    "backtest": backtest,
    "candidate1": candidate1,
    "noise": noise,
    "cliff": cliff,
    "modelside": modelside,
    "correlations": correlations,
}


def main(argv: list[str]) -> None:
    if not argv:
        for report in REPORTS.values():
            report()
        return
    for name in argv:
        report = REPORTS.get(name)
        if report is None:
            print(f"unknown report {name!r}; try one of {', '.join(REPORTS)}")
            continue
        report()


if __name__ == "__main__":
    main(sys.argv[1:])
