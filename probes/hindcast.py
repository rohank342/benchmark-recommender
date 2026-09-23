"""
probes/hindcast.py
==================
The hindcast, recomputed from committed data.

    python probes/hindcast.py

WHY THIS EXISTS. The hindcast was pre-registered in
docs/HINDCAST_PREREGISTRATION.md and run three times, but it was never a
script — each run was done by hand and its table pasted into the
document. FINDINGS.md cited its "2 of 4" as a record of a past run
because there was no way to reproduce it. This is that way.

Writing it found that the recorded rerun violates the design's own
central rule. See MIXED POPULATIONS below.

THE REGISTERED DESIGN, implemented here exactly as written:

  T                 2024-06-01, the backtest's cutoff
  outcome           the full v2 population (archived 2025-03-13), a
                    nine-month horizon, not "today"
  population        Open LLM Leaderboard v2 at BOTH ends, raw columns.
                    Fixed in advance, and quoting the registration:
                    "v2 is the only source where every eligible
                    benchmark shares one model population at both
                    dates. That costs three benchmarks and buys the
                    only version of this test that measures what it
                    claims to."
  eligibility       v2 data at both dates; >= the saturation minimum at
                    T; >= 20 new models by the outcome; and NOT already
                    >= 0.70 saturated at T (the ceiling rule)
  tiering           added at the 2026-09-22 rerun: a thin-tier
                    benchmark cannot be compared with a partial-tier
                    one, which removes MATH Level 5
  predictors        full as-of trust at T, against release-date order
  discordant pair   the OLDER benchmark is ranked BETTER by the scorer,
                    so the two predictors disagree about which will be
                    more saturated later
  scored            the scorer is right on a pair when the benchmark it
                    ranked better is the LESS saturated one at the
                    outcome

MIXED POPULATIONS — the defect this script found, 2026-09-23. The rerun
table in the document reads BIG-Bench Hard's and GPQA Diamond's
saturation AT T from Epoch (81 and 33 models) while reading their
saturation AT THE OUTCOME from v2 (4,575 models). The other three are v2
at both ends. So two of the five rows subtract a v2 number from an Epoch
number, which is the exact failure the registration was written to
avoid, and the bug class CLAUDE.md section 7 records as "COMPARING TWO
BENCHMARKS CAN MEAN COMPARING TWO POPULATIONS".

It is not cosmetic. Under the registered v2-only rule BIG-Bench Hard's
change flips sign (-0.031 -> +0.028) and GPQA Diamond's decline halves
(-0.315 -> -0.168), and those two carry the document's "the outcome
mean-reverted" reading.

This script computes the registered v2-only version, and prints the
recorded table beside it so the difference is visible rather than
silently corrected.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

T = "2024-06-01"
POPULATION = "open_llm_leaderboard_v2"
CEILING_RULE = 0.70  # already this saturated at T -> excluded
MIN_NEW_MODELS = 20

# The five the registration found eligible, plus MATH Level 5, which the
# 2026-09-22 rerun excluded on tiering. Listed rather than discovered so
# that a catalog addition cannot silently change a pre-registered set.
REGISTERED = (
    "MATH Level 5",
    "BIG-Bench Hard",
    "MuSR",
    "GPQA Diamond",
    "MMLU-Pro",
    "IFEval",
)

# The rerun table as committed in docs/HINDCAST_PREREGISTRATION.md on
# 2026-09-22, for comparison only. Never used in a computation.
RECORDED = {
    "MMLU-Pro": (0.130, 0.158),
    "IFEval": (0.217, 0.300),
    "BIG-Bench Hard": (0.216, 0.185),
    "MuSR": (0.361, 0.055),
    "GPQA Diamond": (0.505, 0.190),
}


def _v2_scores(benchmark):
    """The v2 score set for a benchmark, or None if it has none."""
    from cross_source import load_score_sets

    for scores in load_score_sets(benchmark):
        if scores.source == POPULATION:
            return scores
    return None


def run() -> dict:
    from benchmark_scoring import measure_saturation, score_benchmark
    from fetch_benchmarks import find_benchmark

    rows, excluded = [], []
    for name in REGISTERED:
        benchmark = find_benchmark(name)
        scores = _v2_scores(benchmark)
        if scores is None:
            excluded.append((name, "no v2 score set"))
            continue
        at_t = scores.before(T)
        sat_t, _ = measure_saturation(at_t)
        sat_out, _ = measure_saturation(scores)
        if sat_t is None or sat_out is None:
            excluded.append((name, "saturation unmeasurable at one end"))
            continue
        if len(scores.scores) - len(at_t.scores) < MIN_NEW_MODELS:
            excluded.append((name, "fewer than 20 new models by the outcome"))
            continue
        if sat_t >= CEILING_RULE:
            excluded.append((name, f"already {sat_t:.3f} saturated at T — ceiling rule"))
            continue
        trust = score_benchmark(benchmark, as_of=T)
        if trust.evidence_tier == "thin":
            excluded.append((name, "thin tier at T — not comparable across tiers"))
            continue
        rows.append(
            {
                "name": name,
                "released": benchmark.release_date,
                "trust_t": trust.health,
                "tier_t": trust.evidence_tier,
                "sat_t": sat_t,
                "sat_out": sat_out,
                "n_t": len(at_t.scores),
                "n_out": len(scores.scores),
            }
        )
    return {"rows": rows, "excluded": excluded}


def main() -> None:
    result = run()
    rows, excluded = result["rows"], result["excluded"]

    print(f"\nHINDCAST — registered design, v2 population at both ends, T = {T}\n")
    print(
        f"{'benchmark':17}{'released':>11}{'trust@T':>9}{'sat@T':>8}"
        f"{'sat@out':>9}{'change':>9}{'n@T':>6}{'n@out':>7}"
    )
    for r in sorted(rows, key=lambda r: -r["trust_t"]):
        print(
            f"{r['name']:17}{r['released']:>11}{r['trust_t']:>9.1f}"
            f"{r['sat_t']:>8.3f}{r['sat_out']:>9.3f}"
            f"{r['sat_out'] - r['sat_t']:>+9.3f}{r['n_t']:>6}{r['n_out']:>7}"
        )
    print("\nexcluded, with the registered reason:")
    for name, why in excluded:
        print(f"  {name:17} {why}")

    # Discordant pairs: the older benchmark ranked better by the scorer.
    print("\ndiscordant pairs — scorer and release date disagree:\n")
    discordant = right = 0
    for a in rows:
        for b in rows:
            if a["name"] >= b["name"]:
                continue
            older, newer = (a, b) if a["released"] < b["released"] else (b, a)
            if older["trust_t"] <= newer["trust_t"]:
                continue  # concordant: cannot separate the predictors
            discordant += 1
            # The scorer says the older one, which it ranked better, will
            # be the LESS saturated at the outcome. Age says the opposite.
            scorer_right = older["sat_out"] < newer["sat_out"]
            right += scorer_right
            print(
                f"  {older['name']:17}({older['released'][:4]}, trust "
                f"{older['trust_t']:.1f}, sat@out {older['sat_out']:.3f})  vs  "
                f"{newer['name']:17}({newer['released'][:4]}, trust "
                f"{newer['trust_t']:.1f}, sat@out {newer['sat_out']:.3f})"
                f"   scorer {'RIGHT' if scorer_right else 'wrong'}"
            )
    if discordant:
        print(f"\n  scorer right on {right} of {discordant} discordant pairs")
    else:
        print("\n  no discordant pairs — the test is not runnable on this set")
    print(
        "\n  DESCRIPTIVE, as registered before any run. A handful of pairs\n"
        "  drawn from the backtest's own five benchmarks is not evidence in\n"
        "  either direction, and the registration said so in advance."
    )

    # The recorded table beside the computed one.
    print("\n\nRECORDED rerun table (docs/HINDCAST_PREREGISTRATION.md, 2026-09-22)")
    print("compared against the registered v2-only rule:\n")
    print(
        f"{'benchmark':17}{'rec T':>8}{'v2 T':>8}{'rec chg':>9}"
        f"{'v2 chg':>9}   population the recorded T came from"
    )
    by_name = {r["name"]: r for r in rows}
    mismatched = []
    for name, (rec_t, rec_out) in RECORDED.items():
        r = by_name.get(name)
        if r is None:
            print(f"{name:17}{rec_t:>8.3f}{'n/a':>8}   (excluded by the rules above)")
            continue
        drift = abs(rec_t - r["sat_t"]) > 0.005
        if drift:
            mismatched.append(name)
        print(
            f"{name:17}{rec_t:>8.3f}{r['sat_t']:>8.3f}"
            f"{rec_out - rec_t:>+9.3f}{r['sat_out'] - r['sat_t']:>+9.3f}"
            f"   {'EPOCH — MISMATCHED' if drift else 'v2'}"
        )
    if mismatched:
        print(
            f"\n  {len(mismatched)} of {len(RECORDED)} recorded rows read saturation at T\n"
            f"  from Epoch and at the outcome from v2: {', '.join(mismatched)}.\n"
            "  The registration fixed v2 at both ends precisely to prevent\n"
            "  this. BIG-Bench Hard's change flips sign under the rule and\n"
            "  GPQA Diamond's decline halves."
        )


if __name__ == "__main__":
    main()
