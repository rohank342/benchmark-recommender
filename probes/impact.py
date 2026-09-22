"""
probes/impact.py
================
How often does a scoring rule actually fire?

Written 2026-09-22 after ranking two model-side findings as HIGH on the
strength of their mechanism, then measuring them and discovering one
fired on **zero** of 187 benchmark citations and the other on **one**
model/benchmark pair in the whole dataset. A mechanism that is wrong but
never exercised is a guard to add cheaply, not an urgent fix — and the
only way to tell the difference is to count before ranking.

Use it before changing anything:

    python probes/impact.py                 # all the standard reports
    python probes/impact.py citations       # which benchmarks models cite
    python probes/impact.py tiers           # evidence tiers across the catalog
    python probes/impact.py weights         # what dominates model weighting
    python probes/impact.py parameter HEALTHY_SPREAD 0.084 0.24 0.358

Hits the network for nothing; everything comes from committed data.
"""

from __future__ import annotations

import collections
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

MODELS_PATH = ROOT / "data" / "models_raw.json"


def _scored_models():
    """Every model with a composite score, plus its benchmark breakdown."""
    from enrich_scores import build_external_index
    from scoring import score_models

    if not MODELS_PATH.exists():
        print(f"  (no {MODELS_PATH.name} — run fetch_models.py; model reports skipped)")
        return []
    raw = json.loads(MODELS_PATH.read_text())["models"]
    ranked = score_models(raw, index=build_external_index())
    return [m for m in ranked if m.composite_score is not None]


def citations() -> None:
    """Which benchmarks the model side actually cites, recognised or not."""
    from fetch_benchmarks import find_benchmark

    models = _scored_models()
    if not models:
        return
    counts: collections.Counter = collections.Counter()
    models_per: dict[str, set] = collections.defaultdict(set)
    for model in models:
        for point in model.benchmark_breakdown:
            label = point["benchmark"]
            counts[label] += 1
            models_per[label].add(model.model_id)

    total = sum(counts.values())
    print(f"\n{len(models)} scored models, {total} benchmark citations\n")
    print(f"{'benchmark cited':44}{'cites':>7}{'models':>8}  in catalog?")
    cumulative = 0
    for label, n in counts.most_common():
        cumulative += n
        known = find_benchmark(label)
        print(
            f"{label[:43]:44}{n:>7}{len(models_per[label]):>8}  "
            f"{'yes: ' + known.name if known else 'NO'}"
            f"   (cum {cumulative / total:.0%})"
        )


def tiers() -> None:
    """Evidence depth across the catalog, and what it rests on."""
    from benchmark_scoring import score_all_benchmarks

    by_tier: dict[str, list] = collections.defaultdict(list)
    for trust in score_all_benchmarks():
        by_tier[trust.evidence_tier].append(trust)
    print()
    for tier in ("full", "partial", "thin"):
        items = by_tier.get(tier, [])
        print(f"{tier.upper():8} {len(items):2} benchmarks")
        for trust in items:
            print(f"    {trust.benchmark.name[:30]:31}{trust.health:6.1f}  {trust.evidence_summary}")


def weights() -> None:
    """What is actually carrying the weight in model scoring."""
    from fetch_benchmarks import find_benchmark
    from benchmark_scoring import score_all_benchmarks

    models = _scored_models()
    if not models:
        return
    tier_of = {t.benchmark.name: t.evidence_tier for t in score_all_benchmarks()}
    by_tier: collections.Counter = collections.Counter()
    weighted: dict[str, float] = collections.defaultdict(float)
    for model in models:
        for point in model.benchmark_breakdown:
            known = find_benchmark(point["benchmark"])
            tier = tier_of.get(known.name) if known else "unrecognised"
            by_tier[tier] += 1
            weighted[tier] += point["trust"]

    total = sum(by_tier.values())
    print(f"\ncitations by the evidence tier of the benchmark cited ({total} total):\n")
    for tier, n in by_tier.most_common():
        share = weighted[tier] / sum(weighted.values())
        print(f"   {str(tier):14}{n:>5} citations ({n / total:.0%})   "
              f"{share:.0%} of total weight")

    no_weighted = sum(
        1
        for m in models
        if all(not find_benchmark(p["benchmark"]) for p in m.benchmark_breakdown)
    )
    print(f"\n   models resting ENTIRELY on unrecognised benchmarks: "
          f"{no_weighted}/{len(models)} ({no_weighted / len(models):.0%})")


def parameter(name: str, *values: str) -> None:
    """How much does one constant move the catalog?"""
    import benchmark_scoring as bs
    import cross_source as cs
    from benchmark_scoring import score_all_benchmarks

    module = bs if hasattr(bs, name) else cs
    original = getattr(module, name)
    caster = type(original)

    def snapshot():
        ranked = score_all_benchmarks()
        return (
            [t.benchmark.name for t in ranked],
            {t.benchmark.name: t.evidence_tier for t in ranked},
            sum(t.health for t in ranked) / len(ranked),
        )

    base_order, base_tiers, base_mean = snapshot()
    print(f"\n{name} (current {original})\n")
    print(f"{'value':>12}{'rank moves':>12}{'tier changes':>14}{'mean health':>13}")
    try:
        for raw in values:
            setattr(module, name, caster(raw))
            try:
                cs.agreement_for.cache_clear()
            except AttributeError:
                pass
            order, tier_map, mean = snapshot()
            moves = sum(1 for i, n in enumerate(order) if base_order.index(n) != i)
            tier_changes = sum(1 for n, t in tier_map.items() if base_tiers[n] != t)
            print(f"{raw:>12}{moves:>12}{tier_changes:>14}{mean:>13.1f}")
    finally:
        setattr(module, name, original)
        try:
            cs.agreement_for.cache_clear()
        except AttributeError:
            pass


def main(argv: list[str]) -> None:
    if not argv:
        tiers()
        citations()
        weights()
        return
    command, rest = argv[0], argv[1:]
    {"citations": citations, "tiers": tiers, "weights": weights}.get(
        command, lambda: parameter(rest[0], *rest[1:]) if command == "parameter" else
        print(f"unknown report {command!r}")
    )()


if __name__ == "__main__":
    main(sys.argv[1:])
