"""
benchmark_scoring.py
====================
Scores benchmarks, not models.

A benchmark earns trust by still doing its job: separating better models
from worse ones, on material the models haven't memorized, in a way
other people can reproduce, for a task someone actually cares about.
Four factors, each 0-1, combined into a 0-100 trust score:

  discrimination  Does it still spread models out? Measured from the
                  score distribution: when the leaders cluster within a
                  point of each other near the ceiling, the benchmark
                  has stopped answering the question it was built for.
  freshness       How long has the test set been public? Every month
                  after publication is another month for it to appear in
                  a crawl. Decays on a half-life.
  reproducibility How many independent groups publish scores on it,
                  and do those scores agree.
  specificity     How narrowly does it map to a real task? "Resolve this
                  GitHub issue" transfers; "answer multiple-choice
                  questions across 57 subjects" transfers less.

Saturation is *measured* wherever Epoch's export gives per-model scores,
and *curated* otherwise. The breakdown says which, per factor, because a
trust score built on assertions should not look like one built on data.

########################################################################
# TODO(you): the weights and half-life below are judgement calls, not
# fitted parameters. The honest way to calibrate them: take benchmarks
# with known outcomes (HellaSwag and ARC as saturated; SWE-Bench Verified
# and LiveCodeBench as live) and check the ranking puts them where you'd
# expect, then adjust. They are grouped here to make that easy.
########################################################################
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional

from fetch_benchmarks import (
    Benchmark,
    BenchmarkScores,
    load_benchmark_catalog,
    load_benchmark_scores,
)

# How much each factor contributes to the final score. Sums to 1.0.
FACTOR_WEIGHTS = {
    "discrimination": 0.40,
    "freshness": 0.20,
    "reproducibility": 0.20,
    "specificity": 0.20,
}

# A public test set's trust halves every this many days. ~2 years: long
# enough that a recent benchmark isn't punished, short enough that a
# 2018 multiple-choice set scores near zero.
LEAKAGE_HALF_LIFE_DAYS = 730

# Top-k models used to measure how tightly the leaders cluster.
SATURATION_TOP_K = 10

# A spread this wide across the top-k (as a fraction of the usable score
# range) counts as fully discriminating.
HEALTHY_SPREAD = 0.20

# Multipliers applied when a benchmark is publicly flagged. These are
# penalties on the *final* score, since a documented leak undermines
# every factor at once.
CONTAMINATION_PENALTY = 0.65

# Contamination rate at which the full penalty applies. Below it, the
# penalty scales with the measured rate, so a benchmark with 16% of its
# items in a pretraining corpus isn't punished like one with 28%.
FULL_CONTAMINATION_RATE = 0.30

# Observed score inflation at which the full penalty applies. A benchmark
# whose scores collapse by 40% once decontaminated has been telling you
# about memorization, not capability.
FULL_CONTAMINATION_EFFECT = 0.40
REPORTED_SATURATION_PENALTY = 0.80

# Evaluator count at which reproducibility is considered fully
# established — more than this adds nothing.
EVALUATORS_FOR_FULL_CREDIT = 5


@dataclass
class Factor:
    """One component of a trust score, and where its value came from."""

    name: str
    value: float  # 0-1
    weight: float
    basis: str  # "measured", "curated", or "unknown"
    explanation: str

    @property
    def contribution(self) -> float:
        return round(self.value * self.weight * 100, 1)


@dataclass
class BenchmarkTrust:
    benchmark: Benchmark
    trust_score: float  # 0-100
    factors: list[Factor] = field(default_factory=list)
    penalties: list[str] = field(default_factory=list)
    measured_saturation: Optional[float] = None  # 0-1, higher = more saturated
    models_measured: int = 0

    @property
    def dominant_factor(self) -> Optional[Factor]:
        """The factor holding the score back the most."""
        if not self.factors:
            return None
        return min(self.factors, key=lambda f: f.value)

    @property
    def summary(self) -> str:
        """One line explaining the score, for the UI."""
        weakest = self.dominant_factor
        if weakest is None:
            return "No factors available."
        head = f"{weakest.name} is the limiting factor — {weakest.explanation}"
        if self.penalties:
            head += f" Penalized for: {', '.join(self.penalties)}."
        return head


def _days_since(iso_date: Optional[str]) -> Optional[int]:
    if not iso_date:
        return None
    try:
        parsed = datetime.fromisoformat(iso_date).date()
    except ValueError:
        return None
    return (date.today() - parsed).days


def measure_saturation(scores: BenchmarkScores) -> tuple[float, str]:
    """
    How saturated is this benchmark, from its own score distribution?

    Two things make a benchmark stop discriminating: the leaders bunch
    together, and they bunch near the ceiling. A tight cluster at 40% is
    a hard benchmark that everyone fails equally; a tight cluster at 95%
    is a solved one. Both are useless for ranking, so both count.

    Returns (0-1 saturation, explanation).
    """
    usable_range = max(scores.ceiling - scores.random_baseline, 1e-6)
    ranked = sorted(scores.scores, reverse=True)
    top = ranked[:SATURATION_TOP_K]
    if len(top) < 2:
        return 0.5, "too few scores to measure the spread"

    spread = (max(top) - min(top)) / usable_range
    headroom_used = (statistics.mean(top) - scores.random_baseline) / usable_range
    headroom_used = min(max(headroom_used, 0.0), 1.0)

    # Tight spread is the primary signal; proximity to the ceiling
    # compounds it.
    tightness = 1.0 - min(spread / HEALTHY_SPREAD, 1.0)
    saturation = min(1.0, 0.65 * tightness + 0.35 * headroom_used)

    explanation = (
        f"top {len(top)} models span {spread * 100:.1f} points of the usable range "
        f"and average {headroom_used * 100:.0f}% of it"
    )
    return saturation, explanation


def _discrimination_factor(
    benchmark: Benchmark, scores: Optional[BenchmarkScores]
) -> tuple[Factor, Optional[float]]:
    if scores is not None:
        saturation, explanation = measure_saturation(scores)
        return (
            Factor(
                name="discrimination",
                value=1.0 - saturation,
                weight=FACTOR_WEIGHTS["discrimination"],
                basis="measured",
                explanation=explanation
                + f" (from {len(scores.scores)} model scores)",
            ),
            saturation,
        )

    # No score data: fall back to the curated flag.
    if benchmark.saturation_flagged:
        return (
            Factor(
                name="discrimination",
                value=0.2,
                weight=FACTOR_WEIGHTS["discrimination"],
                basis="curated",
                explanation="reported as saturated, but no score data here to measure it",
            ),
            None,
        )
    return (
        Factor(
            name="discrimination",
            value=0.5,
            weight=FACTOR_WEIGHTS["discrimination"],
            basis="unknown",
            explanation="no score distribution available — neutral placeholder",
        ),
        None,
    )


# Age matters less when the test set isn't static. A benchmark that adds
# new items on a rolling basis is scoring models on material published
# after their training cutoff regardless of when the benchmark launched,
# and one that withholds its answers can't leak by being read.
HOLDOUT_AGE_DISCOUNT = {
    "public_static": 1.0,  # full decay
    "refreshed": 0.35,  # ages at about a third the rate
    "private_holdout": 0.0,  # doesn't age this way at all
}
PRIVATE_HOLDOUT_FLOOR = 0.9


def _freshness_factor(benchmark: Benchmark) -> Factor:
    age_days = _days_since(benchmark.release_date)
    if age_days is None:
        return Factor(
            name="freshness",
            value=0.5,
            weight=FACTOR_WEIGHTS["freshness"],
            basis="unknown",
            explanation="no release date recorded",
        )

    discount = HOLDOUT_AGE_DISCOUNT.get(benchmark.holdout, 1.0)
    effective_age = max(age_days, 0) * discount
    value = 0.5 ** (effective_age / LEAKAGE_HALF_LIFE_DAYS)
    if benchmark.holdout == "private_holdout":
        value = max(value, PRIVATE_HOLDOUT_FLOOR)

    years = age_days / 365.25
    if benchmark.holdout == "refreshed":
        explanation = (
            f"launched {years:.1f} years ago but refreshed on a rolling basis, "
            "so what it scores is newer than that"
        )
    elif benchmark.holdout == "private_holdout":
        explanation = f"{years:.1f} years old, but answers are held back from publication"
    elif years > 2:
        explanation = f"public and static for {years:.1f} years, so leakage risk has compounded"
    else:
        explanation = f"published {years:.1f} years ago"

    return Factor(
        name="freshness",
        value=value,
        weight=FACTOR_WEIGHTS["freshness"],
        basis="curated",
        explanation=explanation,
    )


def _reproducibility_factor(benchmark: Benchmark) -> Factor:
    count = max(benchmark.independent_evaluators, 0)
    value = min(count / EVALUATORS_FOR_FULL_CREDIT, 1.0)
    return Factor(
        name="reproducibility",
        value=value,
        weight=FACTOR_WEIGHTS["reproducibility"],
        basis="curated",
        explanation=f"{count} independent evaluator(s) publish scores on it",
    )


def _specificity_factor(benchmark: Benchmark) -> Factor:
    return Factor(
        name="specificity",
        value=min(max(benchmark.task_specificity, 0.0), 1.0),
        weight=FACTOR_WEIGHTS["specificity"],
        basis="curated",
        explanation=(
            "maps narrowly onto a real task"
            if benchmark.task_specificity >= 0.7
            else "broad or proxy-shaped rather than task-shaped"
        ),
    )


def score_benchmark(benchmark: Benchmark) -> BenchmarkTrust:
    """Compute one benchmark's 0-100 trust score, with its breakdown."""
    scores = load_benchmark_scores(benchmark)
    discrimination, saturation = _discrimination_factor(benchmark, scores)
    factors = [
        discrimination,
        _freshness_factor(benchmark),
        _reproducibility_factor(benchmark),
        _specificity_factor(benchmark),
    ]

    raw = sum(factor.value * factor.weight for factor in factors) * 100
    penalties: list[str] = []
    if benchmark.contamination_flagged:
        rate = benchmark.contamination_rate
        effect = benchmark.contamination_effect
        severities = []
        descriptions = []
        if rate is not None:
            severities.append(min(rate / FULL_CONTAMINATION_RATE, 1.0))
            descriptions.append(f"{rate:.0%} of items in pretraining data")
        if effect is not None:
            severities.append(min(effect / FULL_CONTAMINATION_EFFECT, 1.0))
            descriptions.append(f"scores fall {effect:.0%} when decontaminated")

        if severities:
            # Take the worse of the two: a modest overlap rate that
            # nonetheless inflates scores badly is still badly inflated.
            multiplier = 1.0 - (1.0 - CONTAMINATION_PENALTY) * max(severities)
            penalties.append("; ".join(descriptions))
        else:
            multiplier = CONTAMINATION_PENALTY
            penalties.append("reported contamination")
        raw *= multiplier
    if benchmark.saturation_flagged and scores is None:
        # With score data the measurement already reflects this; without
        # it, the flag is all we have.
        raw *= REPORTED_SATURATION_PENALTY
        penalties.append("reported saturation")

    return BenchmarkTrust(
        benchmark=benchmark,
        trust_score=round(min(max(raw, 0.0), 100.0), 1),
        factors=factors,
        penalties=penalties,
        measured_saturation=saturation,
        models_measured=len(scores.scores) if scores else 0,
    )


def score_all_benchmarks() -> list[BenchmarkTrust]:
    """Every catalogued benchmark, most trustworthy first."""
    scored = [score_benchmark(b) for b in load_benchmark_catalog()]
    scored.sort(key=lambda t: t.trust_score, reverse=True)
    return scored


def trust_by_key() -> dict[str, BenchmarkTrust]:
    return {t.benchmark.key: t for t in score_all_benchmarks()}


if __name__ == "__main__":
    print(f"{'benchmark':<32}{'trust':>7}{'saturation':>12}  limiting factor")
    print("-" * 100)
    for trust in score_all_benchmarks():
        saturation = (
            f"{trust.measured_saturation * 100:.0f}% (meas)"
            if trust.measured_saturation is not None
            else "  — (curated)"
        )
        weakest = trust.dominant_factor
        print(
            f"{trust.benchmark.name:<32}{trust.trust_score:>7.1f}{saturation:>12}  "
            f"{weakest.name if weakest else '-'}"
        )
