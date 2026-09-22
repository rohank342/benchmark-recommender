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
from dataclasses import dataclass, field, replace
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
# THE SCORE IS SPLIT IN TWO (owner's decision, 2026-09-22).
#
# Every test this project has run — the HF backtest, Candidate 1 — asks
# whether a benchmark is still a working MEASUREMENT. task_specificity
# answers a different question: whether it is RELEVANT to a task. A
# benchmark can be a perfect measurement of something you do not need,
# and a broken measurement of something you do. Averaging those into one
# number answers neither.
#
# Adopted on that argument ALONE. It does not improve any test result:
# the backtest gets worse (10/12 -> 8/12) and Candidate 1 still fails.
# See docs/SCORE_SPLIT_PROPOSAL.md.
#
# MEASUREMENT HEALTH — the three factors about the measurement itself,
# plus all the penalties. Reweighted PROPORTIONALLY from 0.40/0.20/0.20
# (which summed to 0.80) so that no new weight is chosen: this project
# has more free parameters than validation already.
HEALTH_WEIGHTS = {
    "discrimination": 0.50,
    "freshness": 0.25,
    "reproducibility": 0.25,
}

# TASK RELEVANCE — specificity alone, from rubric v2. Shown separately,
# never multiplied into health.
#
# CURATE(you): relevance is really a property of a (benchmark, task)
# PAIR, not of a benchmark. "Is this task-shaped?" only has an answer
# once you say which task. A per-benchmark relevance score is therefore
# an approximation, and the UI already half-admits it by filtering to a
# task category before showing the number. Scoring relevance per
# (benchmark, task) pair is open work — see docs/SCORE_SPLIT_PROPOSAL.md.
RELEVANCE_FACTOR = "specificity"

# Health factors that have a real measurement path and a weaker proxy to
# fall back on. When one of these falls back, it contributes nothing and
# the rest are renormalized — see score_benchmark. Freshness is
# deliberately absent: it is computed exactly from the release date, so
# there is no measurement for it to be missing.
FALLBACK_CAPABLE = frozenset({"discrimination", "reproducibility"})

# Kept as the union so that anything iterating factor weights still
# works. Health factors carry their health weight; specificity carries
# 1.0 because relevance is its own 0-100 score, not a component.
FACTOR_WEIGHTS = {**HEALTH_WEIGHTS, "specificity": 1.0}

# A public test set's trust halves every this many days. ~2 years: long
# enough that a recent benchmark isn't punished, short enough that a
# 2018 multiple-choice set scores near zero.
LEAKAGE_HALF_LIFE_DAYS = 730

# Top-k models used to measure how tightly the leaders cluster.
# Saturation is measured over the top percentile of a stated population.
# The population is PART of the definition, not a label beside it: the
# top 20% of frontier models and the top 20% of community submissions
# answer different questions, and readings are comparable only within a
# population. See BenchmarkScores.population.
SATURATION_TOP_PERCENTILE = 20.0

# Below this many models a percentile selects too few to mean anything,
# and saturation is reported as unmeasurable rather than estimated from
# a handful. Chosen from the stability table in
# docs/SATURATION_MEASUREMENT.md: the largest improvement step is from
# 10 to 30, and it flattens after.
MIN_SATURATION_POPULATION = 30


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
    # MEASUREMENT HEALTH, 0-100: discrimination, freshness,
    # reproducibility and the penalties. "Does this benchmark still
    # work as a measurement?" The name `trust_score` is kept because
    # every consumer reads it and renaming it would be a silent
    # behaviour change dressed as a rename; `health` is the alias to
    # use in new code.
    trust_score: float  # 0-100
    factors: list[Factor] = field(default_factory=list)
    penalties: list[str] = field(default_factory=list)
    measured_saturation: Optional[float] = None  # 0-1, higher = more saturated
    models_measured: int = 0
    # Saturation per source, since different sources cover different
    # populations: {source: (saturation, n_models)}.
    saturation_by_source: dict = field(default_factory=dict)
    primary_source: Optional[str] = None

    @property
    def evidence_tier(self) -> str:
        """
        How much evidence this score rests on: "full", "partial", "thin".

        DERIVED FROM THE CATALOG, NOT CHOSEN. Counting (factors used,
        factors measured) across all 26 benchmarks on 2026-09-22 gives
        exactly three clusters with nothing in between:

            (3 used, 2 measured)  8 benchmarks   discrimination AND
                                                 reproducibility measured
            (2 used, 1 measured) 15 benchmarks   discrimination measured,
                                                 reproducibility dropped
            (1 used, 0 measured)  3 benchmarks   nothing measured;
                                                 freshness alone

        No threshold had to be invented because no benchmark sits near
        one. If a later catalog fills the gaps, these boundaries stop
        falling out of the data and must be re-derived rather than kept.

        WHY TIERS AND NOT A MULTIPLIER: renormalizing makes a thin score
        arithmetically comparable to a thick one, which is exactly what
        it is not. This is the same argument the model side already
        makes about provenance — a multiplier cannot express "an
        unverified number is not evidence" — applied to benchmarks.
        """
        used = self.evidence["factors_used"]
        measured = len(self.evidence["measured"])
        if measured >= 2 and used >= 3:
            return "full"
        if measured >= 1:
            return "partial"
        return "thin"

    @property
    def tier_rank(self) -> int:
        """0 = most evidence. Sort key; never compare scores across tiers."""
        return {"full": 0, "partial": 1, "thin": 2}[self.evidence_tier]

    @property
    def evidence(self) -> dict:
        """
        What the health score actually rests on.

        Since unmeasurable factors are dropped and the rest renormalized,
        two scores of 70 can mean very different things: one averaged
        over three factors, two of them measured; the other resting
        entirely on a release date. Nothing in the number says which, so
        this does.
        """
        health = [f for f in self.factors if f.name in HEALTH_WEIGHTS]
        carrying = [f for f in health if f.weight > 0]
        return {
            "factors_used": len(carrying),
            "factors_possible": len(health),
            "measured": sorted(f.name for f in carrying if f.basis == "measured"),
            "curated": sorted(f.name for f in carrying if f.basis != "measured"),
            "dropped": sorted(f.name for f in health if f.weight == 0),
        }

    @property
    def evidence_summary(self) -> str:
        """One line for a table cell."""
        e = self.evidence
        parts = [f"{e['factors_used']}/{e['factors_possible']} factors"]
        if e["measured"]:
            parts.append(f"{len(e['measured'])} measured")
        if e["curated"]:
            parts.append(f"{len(e['curated'])} curated")
        if e["dropped"]:
            parts.append("dropped: " + ", ".join(e["dropped"]))
        return "; ".join(parts)

    @property
    def health(self) -> float:
        """Measurement health, 0-100. The same number as trust_score."""
        return self.trust_score

    @property
    def relevance(self) -> float:
        """
        Task relevance, 0-100, from rubric v2. NEVER multiplied into
        health — it answers a different question, and on Candidate 1 it
        overrode a correct discrimination signal eight to one when the
        two were combined.
        """
        return round(self.benchmark.task_specificity * 100, 1)

    @property
    def population(self) -> Optional[str]:
        """
        The model population the headline saturation was measured on.

        Saturation is a property of a population snapshot, not of a
        benchmark (docs/SATURATION_MEASUREMENT.md), so any reader
        comparing two trust scores needs to know whether they were read
        on the same one. This is what the UI surfaces per row.
        """
        from fetch_benchmarks import describe_population

        if self.primary_source is None:
            return None
        return describe_population(self.primary_source)
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


def measure_saturation(scores: BenchmarkScores) -> tuple[Optional[float], str]:
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

    # DEFINITION CHANGED 2026-09-22: the top PERCENTILE of a stated
    # population, not a fixed top-k. See docs/SATURATION_MEASUREMENT.md.
    #
    # Top-k of n is a different question at every n: top 10 of 33 models
    # is the top 30%, top 10 of 4,575 is the top 0.2%. That artifact
    # alone moved readings by up to 0.81 with no change to the
    # benchmark. A fixed fraction asks "how do the best fifth of THIS
    # population look?" at every size.
    #
    # 20% was chosen from the data, not preferred: across 20
    # cohort-vs-full-population pairs it is the most stable band at
    # every minimum-population threshold tested (mean |delta| 0.052-0.076
    # against 0.113-0.170 for top-10), and it is the most stable by
    # roughly 2x over every alternative. It answers a broader question
    # than top-10 did, which is the honest cost.
    if len(ranked) < MIN_SATURATION_POPULATION:
        return None, (
            f"only {len(ranked)} models scored; "
            f"{MIN_SATURATION_POPULATION} needed for a percentile to mean anything"
        )

    k = max(2, int(round(len(ranked) * SATURATION_TOP_PERCENTILE / 100.0)))
    top = ranked[:k]

    spread = (max(top) - min(top)) / usable_range
    headroom_used = (statistics.mean(top) - scores.random_baseline) / usable_range
    headroom_used = min(max(headroom_used, 0.0), 1.0)

    # Tight spread is the primary signal; proximity to the ceiling
    # compounds it.
    tightness = 1.0 - min(spread / HEALTHY_SPREAD, 1.0)
    saturation = min(1.0, 0.65 * tightness + 0.35 * headroom_used)

    explanation = (
        f"the top {SATURATION_TOP_PERCENTILE:.0f}% of {len(ranked)} "
        f"{scores.population} ({len(top)} models) span {spread * 100:.1f} points "
        f"of the usable range and average {headroom_used * 100:.0f}% of it"
    )
    return saturation, explanation


def _discrimination_factor(
    benchmark: Benchmark,
    scores: Optional[BenchmarkScores],
    as_of: Optional[str] = None,
) -> tuple[Factor, Optional[float]]:
    if scores is not None:
        saturation, explanation = measure_saturation(scores)
    if scores is not None and saturation is None:
        # Too small a population for a percentile to mean anything. Not
        # a measurement, so it must not be scored as one — fall through
        # to the curated path, which the drop-and-renormalize rule then
        # excludes entirely.
        scores = None
    if scores is not None:
        population = describe_population(scores.source)
        detail = f"{explanation}, across {len(scores.scores)} {population}"

        # Where another source covers a different population, say so —
        # a benchmark can be saturated at the frontier and still spread
        # out weaker models, and conflating the two misleads.
        others = [
            (s.source, value)
            for s in load_score_sets(benchmark)
            if s.source != scores.source
            for value in [measure_saturation(s)[0]]
            if value is not None
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

    # Health is the weighted health factors; relevance is kept out of it
    # entirely and reported alongside.
    # DECISION 2026-09-22 (owner), mirroring contamination treatment (c):
    # a health factor that cannot be MEASURED contributes nothing, and
    # the remaining health factors are renormalized to carry full weight.
    #
    # Why: the curated evaluator-count fallback was more generous than
    # the measurement it stood in for (curated mean 0.580 against
    # measured 0.485), so being uncheckable paid better than being
    # checked. That is the same error as the old flat contamination
    # penalty, and it is fixed the same way — absence of measurement is
    # not a finding, in either direction.
    #
    # The cost, which is real: a benchmark with one evaluator and one
    # with five now score identically on this axis. That count is weak
    # evidence, but it is evidence, and this discards it. The UI reports
    # how many factors a score rests on so the discarding is visible.
    # FRESHNESS IS NOT SUBJECT TO THIS RULE. Its basis is "curated"
    # because the release date is curated, but it is not a proxy standing
    # in for a missing measurement — it is computed exactly, from a date
    # that is known. The rule applies only to factors that HAVE a
    # measurement path and fell back off it: discrimination (measured
    # saturation, else the saturation_flagged flag) and reproducibility
    # (cross-source scatter, else an evaluator count).
    dropped = {
        f.name
        for f in factors
        if f.name in FALLBACK_CAPABLE and f.basis != "measured"
    }
    kept = [f for f in factors if f.name in HEALTH_WEIGHTS and f.name not in dropped]
    if kept:
        total = sum(f.weight for f in kept)
        factors = [
            replace(f, weight=f.weight / total)
            if f.name in HEALTH_WEIGHTS and f.name not in dropped
            else (
                replace(
                    f,
                    weight=0.0,
                    explanation=f.explanation + " — not measurable, so excluded",
                )
                if f.name in dropped
                else f
            )
            for f in factors
        ]
    # If NOTHING is measurable the curated signals are all there is, so
    # they are kept at their original weights rather than producing a
    # score of zero. That case is reported as such rather than hidden.
    raw = sum(f.value * f.weight for f in factors if f.name in HEALTH_WEIGHTS) * 100
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
            # The basis changes the wording only; see
            # Benchmark.contamination_effect_basis. A drop measured
            # against a difficulty-matched set means something different
            # from a drop against an unmatched one, and the reader
            # deserves to know which they are looking at.
            if benchmark.contamination_effect_basis == "difficulty_controlled":
                descriptions.append(
                    f"scores fall {effect:.0%} on a difficulty-matched fresh set"
                )
            else:
                descriptions.append(
                    f"scores fall {effect:.0%} on a variant whose difficulty "
                    "was not controlled, so part of that is difficulty rather "
                    "than memorization"
                )

        if severities:
            # Take the worse of the two: a modest overlap rate that
            # nonetheless inflates scores badly is still badly inflated.
            multiplier = 1.0 - (1.0 - CONTAMINATION_PENALTY) * max(severities)
            penalties.append("; ".join(descriptions))
        else:
            # DECISION 2026-09-21 (owner): a flag with no measured rate and
            # no measured effect carries NO numeric penalty. It is surfaced
            # as a warning instead.
            #
            # The flat penalty this replaces was CONTAMINATION_PENALTY,
            # which is identical to what severity = 1 produces — so an
            # unmeasured flag cost as much as contamination measured at the
            # worst level in the catalog, and measuring bought nothing.
            # HumanEval, with a 13% overlap rate and a 39.4% observed
            # effect, landed on 0.655 against an unmeasured flag's 0.650.
            #
            # The alternative was a half-severity charge, which would have
            # required inventing a severity the evidence does not contain.
            # This route keeps the scoring path free of unsourced numbers
            # and matches how item_error_rate=None is already treated:
            # absence of measurement is not a finding.
            #
            # It understates real harm where the harm is real but nobody
            # has counted it — SWE-Bench Verified is the live example — so
            # the warning has to be loud rather than quiet.
            multiplier = 1.0
            penalties.append(
                "WARNING: contamination reported but never quantified "
                "— no penalty applied"
            )
        raw *= multiplier
    # None means nobody has audited this benchmark, which is not the same
    # as a clean audit — so it must not be read as zero.
    if benchmark.item_error_rate is not None and benchmark.known_at(
        "item_error_rate", as_of
    ):
        severity = min(benchmark.item_error_rate / FULL_ITEM_ERROR_RATE, 1.0)
        raw *= 1.0 - (1.0 - ITEM_ERROR_PENALTY) * severity
        # The basis changes the wording only. A demonstrated floor of 16%
        # and a measured 16% are the same amount of known breakage, and
        # scoring a bound more harshly would mean assigning a severity the
        # audit never established. See Benchmark.item_error_rate_basis.
        qualifier = (
            "at least " if benchmark.item_error_rate_basis == "lower_bound" else ""
        )
        penalties.append(
            f"{qualifier}{benchmark.item_error_rate:.0%} of items are "
            "mislabelled or misgraded"
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
            s.source: (round(value, 3), len(s.scores))
            for s in load_score_sets(benchmark)
            for value in [measure_saturation(s)[0]]
            if value is not None
        },
        primary_source=scores.source if scores else None,
        agreement=agreement_for(benchmark) if as_of is None else None,
    )


def score_all_benchmarks(as_of: Optional[str] = None) -> list[BenchmarkTrust]:
    """
    Every catalogued benchmark, TIERED BY EVIDENCE DEPTH then ranked by
    health within a tier.

    A benchmark whose score rests on one factor is never shown above one
    resting on three, whatever the numbers say. That asserts something:
    that a ranking is for deciding what to believe, and more evidence
    outranks a higher number computed from less.
    """
    scored = [score_benchmark(b, as_of) for b in load_benchmark_catalog()]
    scored.sort(key=lambda t: (t.tier_rank, -t.trust_score))
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
