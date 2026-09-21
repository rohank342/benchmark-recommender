"""
backtest.py
===========
Does the trust score agree with a judgement that was already made?

In June 2024 Hugging Face retired six benchmarks from the Open LLM
Leaderboard because they had saturated — ARC, HellaSwag, MMLU,
TruthfulQA, Winogrande, GSM8K — and replaced them with a harder set:
MMLU-Pro, GPQA, MuSR, IFEval, BBH and MATH Lvl 5. That is a dated
expert decision about exactly the property this project scores, which
makes it the closest thing to ground truth available.

Four of the retired and four of the replacements are in this catalog.
The test: scored as of 2024-06-01, do the retired four rank below the
replacements?

WHAT KEEPS THIS HONEST

The saturation flags on the retired four are *derived from the
retirement*. Handing them to a scorer being tested against that same
retirement would be marking its own homework. They are dated to the
announcement (2024-06-26) in the catalog, so as-of scoring at
2024-06-01 cannot see them — along with every other piece of evidence
published after the cutoff, and every model uploaded after it.

What remains available to the scorer at the cutoff is: score
distributions from models that existed by then, release dates, task
specificity, evaluator counts, and any contamination or item-quality
study already published. That is genuinely what someone could have
known in May 2024.

RUN

    python backtest.py            # the test, then the trajectory
    python backtest.py --sweep    # + weight sensitivity

Findings and caveats are written up in docs/BACKTEST.md. The headline
caveat belongs here too: eight benchmarks and one decision is a very
small ground truth, and passing this does not make the weights correct.
"""

from __future__ import annotations

import argparse
import statistics
from dataclasses import dataclass
from typing import Optional

import benchmark_scoring
from benchmark_scoring import FACTOR_WEIGHTS, score_benchmark
from fetch_benchmarks import find_benchmark

CUTOFF = "2024-06-01"

# The four retired benchmarks present in this catalog (of six retired).
# Winogrande and GSM8K are not catalogued, so they sit out.
RETIRED = ["ARC (AI2 Reasoning Challenge)", "HellaSwag", "MMLU", "TruthfulQA"]
# The four replacements present in this catalog (of six chosen).
# MuSR and IFEval are not catalogued.
REPLACEMENTS = ["MMLU-Pro", "GPQA Diamond", "BIG-Bench Hard", "MATH Level 5"]


@dataclass
class Outcome:
    name: str
    label: str  # "retired" or "replacement"
    score: float
    models_used: int
    rank: int = 0


def run_retirement_test(as_of: str = CUTOFF) -> list[Outcome]:
    """Score the eight benchmarks as of the cutoff and rank them."""
    outcomes = []
    for name, label in [(n, "retired") for n in RETIRED] + [
        (n, "replacement") for n in REPLACEMENTS
    ]:
        benchmark = find_benchmark(name)
        if benchmark is None:
            raise SystemExit(f"{name!r} is not in the catalog")
        trust = score_benchmark(benchmark, as_of=as_of)
        outcomes.append(
            Outcome(name, label, trust.trust_score, trust.models_measured)
        )

    outcomes.sort(key=lambda o: -o.score)
    for position, outcome in enumerate(outcomes, start=1):
        outcome.rank = position
    return outcomes


def confusion(outcomes: list[Outcome]) -> dict[str, int]:
    """
    Treat the scorer's bottom four as its "would have retired" set and
    compare against what HF actually retired.
    """
    predicted_retire = {o.name for o in sorted(outcomes, key=lambda o: o.score)[:4]}
    matrix = {"true_retire": 0, "false_retire": 0, "true_keep": 0, "false_keep": 0}
    for outcome in outcomes:
        flagged = outcome.name in predicted_retire
        if outcome.label == "retired":
            matrix["true_retire" if flagged else "false_keep"] += 1
        else:
            matrix["false_retire" if flagged else "true_keep"] += 1
    return matrix


def separation(outcomes: list[Outcome]) -> tuple[bool, float]:
    """
    Perfect separation means every replacement outranks every retired
    benchmark. The gap is worst replacement minus best retired: positive
    means clean separation, negative means overlap.
    """
    retired = [o.score for o in outcomes if o.label == "retired"]
    replacements = [o.score for o in outcomes if o.label == "replacement"]
    return min(replacements) > max(retired), min(replacements) - max(retired)


def print_test(outcomes: list[Outcome]) -> None:
    print(f"\nRETIREMENT TEST — scored as of {CUTOFF}")
    print(f"{'rank':<6}{'benchmark':<30}{'actual':<14}{'trust':>7}{'models':>9}")
    print("-" * 68)
    for o in outcomes:
        marker = "RETIRED" if o.label == "retired" else "kept"
        print(f"{o.rank:<6}{o.name:<30}{marker:<14}{o.score:>7.1f}{o.models_used:>9}")

    matrix = confusion(outcomes)
    clean, gap = separation(outcomes)
    print("\nConfusion matrix (scorer's bottom 4 = 'would have retired'):")
    print(f"{'':<22}{'HF retired':>14}{'HF kept':>12}")
    print(f"{'scorer: retire':<22}{matrix['true_retire']:>14}{matrix['false_retire']:>12}")
    print(f"{'scorer: keep':<22}{matrix['false_keep']:>14}{matrix['true_keep']:>12}")
    correct = matrix["true_retire"] + matrix["true_keep"]
    print(f"\n{correct}/8 correct. Perfect separation: {clean} (gap {gap:+.1f} points)")


def print_trajectory() -> None:
    """Did the 2024 replacements age the way the scorer says they should?"""
    print("\n\nTRAJECTORY — the replacements, then and now")
    print(f"{'benchmark':<24}{'Jun 2024':>10}{'today':>10}{'change':>10}   saturation now")
    print("-" * 78)
    for name in REPLACEMENTS:
        benchmark = find_benchmark(name)
        then = score_benchmark(benchmark, as_of=CUTOFF)
        now = score_benchmark(benchmark)
        saturation = (
            f"{now.measured_saturation * 100:.0f}%"
            if now.measured_saturation is not None
            else "—"
        )
        print(
            f"{name:<24}{then.trust_score:>10.1f}{now.trust_score:>10.1f}"
            f"{now.trust_score - then.trust_score:>+10.1f}   {saturation}"
        )


def sweep_weights() -> None:
    """
    How much does the result depend on the exact weighting?

    A conclusion that survives only at one setting is overfit to eight
    data points. Each factor's weight is varied while the others absorb
    the difference proportionally.
    """
    print("\n\nSENSITIVITY — varying one weight at a time")
    print(f"{'factor':<18}{'weight':>8}{'correct':>9}{'separated':>11}{'gap':>8}")
    print("-" * 56)
    original = dict(FACTOR_WEIGHTS)
    try:
        for factor in original:
            for weight in (0.1, 0.2, 0.3, 0.4, 0.5, 0.6):
                others = [f for f in original if f != factor]
                remainder = 1.0 - weight
                original_others = sum(original[f] for f in others)
                for other in others:
                    FACTOR_WEIGHTS[other] = remainder * (
                        original[other] / original_others
                    )
                FACTOR_WEIGHTS[factor] = weight

                outcomes = run_retirement_test()
                matrix = confusion(outcomes)
                clean, gap = separation(outcomes)
                correct = matrix["true_retire"] + matrix["true_keep"]
                print(
                    f"{factor:<18}{weight:>8.2f}{correct:>7}/8{str(clean):>11}{gap:>+8.1f}"
                )
            FACTOR_WEIGHTS.update(original)
    finally:
        FACTOR_WEIGHTS.clear()
        FACTOR_WEIGHTS.update(original)


def single_factor_analysis() -> None:
    """
    Is any one factor carrying the whole result?

    The retired benchmarks are also the older ones, so a scorer that did
    nothing but rank by age would look like it works. If freshness alone
    separates them, this test mostly confirms "newer benchmarks are
    newer" — a much weaker claim than it appears. Each factor is run at
    weight 1.0 with the others at 0.
    """
    print("\n\nSINGLE-FACTOR — can one factor do it alone?")
    print(f"{'factor alone':<20}{'correct':>9}{'separated':>11}{'gap':>8}")
    print("-" * 50)
    original = dict(FACTOR_WEIGHTS)
    try:
        for factor in original:
            for name in FACTOR_WEIGHTS:
                FACTOR_WEIGHTS[name] = 1.0 if name == factor else 0.0
            outcomes = run_retirement_test()
            matrix = confusion(outcomes)
            clean, gap = separation(outcomes)
            correct = matrix["true_retire"] + matrix["true_keep"]
            print(f"{factor:<20}{correct:>7}/8{str(clean):>11}{gap:>+8.1f}")
    finally:
        FACTOR_WEIGHTS.clear()
        FACTOR_WEIGHTS.update(original)

    # The trivial baseline: rank purely by release date, no scoring at all.
    dated = []
    for name in RETIRED + REPLACEMENTS:
        benchmark = find_benchmark(name)
        label = "retired" if name in RETIRED else "replacement"
        dated.append((benchmark.release_date or "", name, label))
    dated.sort(reverse=True)
    newest_four = {name for _, name, _ in dated[:4]}
    baseline_correct = sum(
        1
        for _, name, label in dated
        if (name in newest_four) == (label == "replacement")
    )
    print(f"\n{'release date alone':<20}{baseline_correct:>7}/8   (no scoring, just age order)")
    print("   order: " + ", ".join(f"{n} ({d[:4]})" for d, n, _ in dated))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sweep", action="store_true", help="run the weight sweep")
    args = parser.parse_args()

    outcomes = run_retirement_test()
    print_test(outcomes)
    print_trajectory()
    if args.sweep:
        single_factor_analysis()
        sweep_weights()

    print(
        "\n\nEight benchmarks and one retirement decision. This can falsify the "
        "scorer, not validate it — see docs/BACKTEST.md."
    )


if __name__ == "__main__":
    main()
