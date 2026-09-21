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

from cross_source import agreement_for, reproducibility_from_agreement
from fetch_benchmarks import (
    Benchmark,
    BenchmarkScores,
    describe_population,
    load_benchmark_catalog,
    load_benchmark_scores,
    load_score_sets,
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

# Item quality is a penalty, not a fifth factor. The four factors ask
# how much a benchmark's *scores* are worth; a wrong answer key is a
# defect that undermines all four at once, the same shape as
# contamination. A benchmark cannot compensate for scoring against
# wrong labels by being fresh or task-specific.
#
# Rate at which the full penalty applies, and the floor it applies. 20%
# is deliberately short of "most items are wrong": at that level the
# ranking a benchmark produces is substantially an artifact of its
# errors, and Gema et al. showed that fixing MMLU's 6.49% was already
# enough to reorder models.
# TODO(you): both numbers are judgement calls, like the other knobs here.
FULL_ITEM_ERROR_RATE = 0.20
ITEM_ERROR_PENALTY = 0.60

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
    # Saturation per source, since different sources cover different
    # populations: {source: (saturation, n_models)}.
    saturation_by_source: dict = field(default_factory=dict)
    primary_source: Optional[str] = None
    agreement: Optional[object] = None  # cross_source.AgreementReport, when any

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


def _days_since(iso_date: Optional[str], as_of: Optional[str] = None) -> Optional[int]:
    """Days from `iso_date` to `as_of` (default today)."""
    if not iso_date:
        return None
    try:
        parsed = datetime.fromisoformat(iso_date).date()
        reference = datetime.fromisoformat(as_of).date() if as_of else date.today()
    except ValueError:
        return None
    return (reference - parsed).days


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
    benchmark: Benchmark,
    scores: Optional[BenchmarkScores],
    as_of: Optional[str] = None,
) -> tuple[Factor, Optional[float]]:
    if scores is not None:
        saturation, explanation = measure_saturation(scores)
        population = describe_population(scores.source)
        detail = f"{explanation}, across {len(scores.scores)} {population}"

        # Where another source covers a different population, say so —
        # a benchmark can be saturated at the frontier and still spread
        # out weaker models, and conflating the two misleads.
        others = [
            (s.source, measure_saturation(s)[0])
            for s in load_score_sets(benchmark)
            if s.source != scores.source
        ]
        divergent = [
            (source, value) for source, value in others if abs(value - saturation) > 0.15
        ]
        if divergent:
            detail += ". Note: " + "; ".join(
                f"{value * 100:.0f}% among {describe_population(source)}"
                for source, value in divergent
            )

        return (
            Factor(
                name="discrimination",
                value=1.0 - saturation,
                weight=FACTOR_WEIGHTS["discrimination"],
                basis="measured",
                explanation=detail,
            ),
            saturation,
        )

    # No score data: fall back to the curated flag, if it was known then.
    if benchmark.saturation_flagged and benchmark.known_at("saturation_flagged", as_of):
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
    # 0.6 rather than a midpoint 0.5: hiding the grading material blocks
    # memorizing the answer key, but the task text itself is still public
    # and crawlable, so a model can be trained on the questions and on
    # discussion of them. That is a partial defence, and the discount sits
    # deliberately nearer "public" than "private" to say so.
    "partial_holdout": 0.6,
    "private_holdout": 0.0,  # doesn't age this way at all
}
PRIVATE_HOLDOUT_FLOOR = 0.9


def _freshness_factor(benchmark: Benchmark, as_of: Optional[str] = None) -> Factor:
    age_days = _days_since(benchmark.release_date, as_of)
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
    elif benchmark.holdout == "partial_holdout":
        explanation = (
            f"{years:.1f} years old, but the grading material is withheld, so "
            "the questions can leak without the answer key following"
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


def _reproducibility_factor(
    benchmark: Benchmark, as_of: Optional[str] = None
) -> Factor:
    """
    Whether independent evaluators agree, measured where two comparable
    sources cover the benchmark and counted where they don't.

    The curated evaluator count is a proxy: it says how many groups
    publish a number, not whether those numbers match. Where the data
    allows, the measurement replaces it — and the two can point opposite
    ways. GPQA Diamond has several evaluators (a high proxy) and 8 points
    of unexplained scatter between two of them (a low measurement).
    """
    # Cross-source agreement is computed from today's score sets. Under
    # as-of scoring it is unavailable rather than recomputed: the sources
    # publishing it may not have existed then, and pretending otherwise
    # would import the future through the back door.
    report = agreement_for(benchmark) if as_of is None else None
    measured = reproducibility_from_agreement(report) if report else None

    if measured is not None:
        return Factor(
            name="reproducibility",
            value=measured,
            weight=FACTOR_WEIGHTS["reproducibility"],
            basis="measured",
            explanation=report.describe(),
        )

    count = max(benchmark.independent_evaluators, 0)
    value = min(count / EVALUATORS_FOR_FULL_CREDIT, 1.0)
    explanation = f"{count} independent evaluator(s) publish scores on it"
    if report is not None and not report.comparable:
        # Say why the better measurement wasn't available, rather than
        # letting the count quietly stand in for it.
        explanation += f" — cross-source check unavailable ({report.reason})"
    return Factor(
        name="reproducibility",
        value=value,
        weight=FACTOR_WEIGHTS["reproducibility"],
        basis="curated",
        explanation=explanation,
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


def score_benchmark(
    benchmark: Benchmark, as_of: Optional[str] = None
) -> BenchmarkTrust:
    """
    Compute one benchmark's 0-100 trust score, with its breakdown.

    `as_of` scores the benchmark as it would have looked on a past date:
    only models released before then count toward saturation, freshness
    is measured to that date, and curated claims are used only where
    `evidence_dates` shows they were public by then. Undated evidence and
    undated models are excluded rather than assumed — a backtest that
    quietly uses tomorrow's knowledge proves nothing.
    """
    scores = load_benchmark_scores(benchmark)
    if as_of is not None and scores is not None:
        scores = scores.before(as_of)
        if len(scores.scores) < 2:
            # Nothing measurable existed yet; fall back to curated signals
            # rather than reading a distribution of one.
            scores = None
    discrimination, saturation = _discrimination_factor(benchmark, scores, as_of)
    factors = [
        discrimination,
        _freshness_factor(benchmark, as_of),
        _reproducibility_factor(benchmark, as_of),
        _specificity_factor(benchmark),
    ]

    raw = sum(factor.value * factor.weight for factor in factors) * 100
    penalties: list[str] = []
    if benchmark.contamination_flagged and benchmark.known_at("contamination_flagged", as_of):
        rate = (
            benchmark.contamination_rate
            if benchmark.known_at("contamination_rate", as_of)
            else None
        )
        effect = (
            benchmark.contamination_effect
            if benchmark.known_at("contamination_effect", as_of)
            else None
        )
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
    # None means nobody has audited this benchmark, which is not the same
    # as a clean audit — so it must not be read as zero.
    if benchmark.item_error_rate is not None and benchmark.known_at(
        "item_error_rate", as_of
    ):
        severity = min(benchmark.item_error_rate / FULL_ITEM_ERROR_RATE, 1.0)
        raw *= 1.0 - (1.0 - ITEM_ERROR_PENALTY) * severity
        penalties.append(
            f"{benchmark.item_error_rate:.0%} of items are mislabelled or misgraded"
        )

    if (
        benchmark.saturation_flagged
        and scores is None
        and benchmark.known_at("saturation_flagged", as_of)
    ):
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
        saturation_by_source={
            s.source: (round(measure_saturation(s)[0], 3), len(s.scores))
            for s in load_score_sets(benchmark)
        },
        primary_source=scores.source if scores else None,
        agreement=agreement_for(benchmark) if as_of is None else None,
    )


def score_all_benchmarks(as_of: Optional[str] = None) -> list[BenchmarkTrust]:
    """Every catalogued benchmark, most trustworthy first."""
    scored = [score_benchmark(b, as_of) for b in load_benchmark_catalog()]
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
