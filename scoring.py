"""
scoring.py
==========
Turns raw benchmark numbers (from the Hub card + enrich_scores.py's
external sources) into one composite, rankable score per model.

Model scores are downstream of benchmark scores. A number is only worth
as much as the benchmark that produced it, so every data point is
weighted by that benchmark's trust score from benchmark_scoring.py: 92%
on HumanEval (trust 21, saturated and old) moves a model's score far
less than 40% on SWE-Bench Verified.

Pipeline:
  1. Collect every benchmark data point available for a model (Hub
     card `model-index` results + Artificial Analysis + Epoch AI).
  2. Normalize each to a 0-1 scale.
  3. Average them, weighted by benchmark measurement health (0-100 from
     benchmark_scoring.py), into a raw benchmark score (0-1).
  4. Apply a "source trust discount" — a separate 0-1 multiplier for
     how the number was *reported*: few independent sources, stale
     results, or self-reported on the model's own card.
  5. composite_score = raw_benchmark_score * trust_score
     (benchmark weighting uses measurement HEALTH only — see
     benchmark_scoring.HEALTH_WEIGHTS and docs/SCORE_SPLIT_PROPOSAL.md)

Two distinct trusts are in play and worth keeping straight: how much to
believe the *benchmark* (step 3) and how much to believe the *report* of
a model's result on it (step 4).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from benchmark_scoring import BenchmarkTrust, trust_by_key
from enrich_scores import ExternalScore, ExternalScoreIndex, build_external_index
from fetch_benchmarks import find_benchmark

# REMOVED FROM SCORING 2026-09-22 (owner's decision, option (iii)).
#
# There used to be an UNKNOWN_BENCHMARK_TRUST = 45.0 here: the weight
# given to a result on a benchmark the catalog has never assessed. It was
# CHOSEN, not derived — the pivot commit (e965175) called it "middling on
# purpose" and left a TODO to shrink it as the catalog grew — and it then
# survived two changes to the scale it was expressed in.
#
# An unassessed benchmark now forms its own tier BELOW thin: it carries
# no weight, and its result is shown as unweighted evidence. A model
# whose every result is unassessed is not ranked against models with
# weighted evidence; it is displayed with its numbers and a note saying
# so.
#
# Why not re-derive it: any derivation from the health distribution has
# to pick a statistic, which is the same invented choice the old value
# made, and it would move every time a benchmark is added. Under Reading
# B the model tab's job is to inform, not to rank on a default.
#
# The constant is gone rather than set to zero, so nothing can read it
# back. Nothing else in the codebase used it.
# COMPOSITE INDEXES are not benchmarks. They are published aggregates
# over several benchmarks, and counting one as a benchmark double-counts
# any component the catalog already assesses separately.
#
# Owner's decision 2026-09-22 (D4): excluded from weighting — which D3
# already achieves, since no composite is in the catalog — and MARKED,
# with its known components listed, so a reader can see what it contains
# and what is being counted twice.
#
# COMPONENTS ARE VERSION-DEPENDENT AND THIS IS A SNAPSHOT. Artificial
# Analysis restructured its index at v4.0 (2026-01-06) and again at v4.3
# (2026-09-07); the components below are what its published methodology
# listed on 2026-09-22. The cached scores in data/artificial_analysis.json
# were fetched 2026-09-18 and may have been produced under a different
# component set. Verified from
# https://artificialanalysis.ai/methodology/intelligence-benchmarking
COMPOSITE_COMPONENTS = {
    "artificial_analysis_coding_index": ("Terminal-Bench 4.0", "SciCode"),
}

UNASSESSED_TIER_NOTE = (
    "every benchmark this model reports on is outside the catalog"
)

# --- Trust discount tuning knobs -------------------------------------
# TODO(you): these are reasonable starting guesses, not calibrated
# against real outcomes. Revisit once you have real Epoch AI /
# Artificial Analysis data flowing in.

# Multiplier applied per independent source reporting a score, capped
# at 1.0. e.g. 1 source -> 0.6, 2 sources -> 0.8, 3+ sources -> 1.0
SOURCE_COUNT_WEIGHTS = {1: 0.6, 2: 0.8}
SOURCE_COUNT_WEIGHTS_DEFAULT = 1.0  # 3+ independent sources

# Staleness half-life in days: a benchmark reported this long ago has
# its trust contribution halved. Benchmarks (and the models they were
# run on) age quickly as training data windows creep forward.
STALENESS_HALF_LIFE_DAYS = 270  # ~9 months

# Flat penalty multiplier applied when a model's only benchmark numbers
# come from its own model card, with no independent source reporting it.
# Self-reported scores are the least reliable data in the pipeline: the
# publisher chooses which benchmarks to show and runs them itself.
# TODO(you): tune once there's enough coverage to compare self-reported
# card numbers against independent runs of the same model.
SELF_REPORT_PENALTY = 0.5

# The source name used for benchmark numbers taken off the Hub card.
HUB_CARD_SOURCE = "huggingface_hub_card"


@dataclass
class ScoredModel:
    model_id: str
    params_billion: Optional[float]
    license: Optional[str]
    downloads: int
    raw_benchmark_score: Optional[float]  # 0-1, average of normalized data points
    trust_score: Optional[float]  # 0-1
    composite_score: Optional[float]  # raw_benchmark_score * trust_score
    num_sources: int
    benchmark_points_used: int
    self_reported_only: bool  # every number came from the model's own card
    provenance_verified: bool = True  # repo confirmed to be the benchmarked weights
    sources: list[str] = field(default_factory=list)
    # Which benchmarks produced this score, and what each was worth:
    # [{benchmark, trust, score, source}], most influential first.
    benchmark_breakdown: list[dict[str, Any]] = field(default_factory=list)
    # True when at least one result is on a benchmark the catalog has
    # assessed and can weight. False when every result is unassessed or
    # thin-tier — such a model is shown, not ranked.
    has_weighted_evidence: bool = False
    # Do the sources that report the SAME benchmark for this model agree?
    #   True  — two or more sources checked, and they agree
    #   False — two or more sources checked, and they contradict
    #   None  — nothing to check: no benchmark has two sources
    # See _sources_agree.
    sources_agree: Optional[bool] = None


@dataclass
class _DataPoint:
    """One normalized benchmark result, with the weight it carries."""

    value: float  # 0-1
    benchmark_label: str  # what the source called it
    benchmark_key: Optional[str]  # catalog key, if recognized
    benchmark_trust: float  # 0-100
    source: str
    # DECISION 2026-09-22 (owner), option (ii): a benchmark whose health
    # score rests on no measured factor at all — THIN tier — carries NO
    # weight here. Its result is still reported, as unweighted evidence
    # beside the score.
    #
    # Why: a thin health score is computed from a release date. Letting
    # it weight a model's result would reintroduce, one layer down, the
    # inversion evidence tiering was added to stop.
    #
    # IT CHANGES NOTHING TODAY. No model result in data/models_raw.json
    # cites a thin-tier benchmark — 0 of 187 citations, measured with
    # probes/impact.py. This is a guard, adopted because it invents no
    # parameter and matches the dossier framing: evidence that cannot
    # carry weight is shown rather than discarded.
    unweighted: bool = False
    # Which configuration produced this number, where the source says.
    # "pass@1" / "pass@100" from a Hub card's metric_name, or
    # "Edit format=diff" / "Agent=Codex CLI" from an Epoch column.
    config: Optional[str] = None
    # Why this point carries no weight, for the UI. Set only when
    # `unweighted` was decided by the repeated-label rule below.
    unweighted_reason: Optional[str] = None

    @property
    def weight(self) -> float:
        if self.unweighted:
            return 0.0
        return self.benchmark_trust / 100.0


# DECISION D5 (owner, 2026-09-23), option (iii): where a benchmark
# documents a canonical protocol, the entry matching it is weighted and
# the others are shown as unweighted evidence with their configuration
# named. Where no canonical protocol is documented, NOTHING is picked
# and NOTHING is averaged — every entry is shown unweighted with a
# CURATE note saying what is missing.
#
# The rule for each benchmark has to come from THAT BENCHMARK'S OWN
# definition — its paper or its official leaderboard — not from a
# preference of this repo's. An unsourced pick would be inventing a
# protocol, which section 3 of CLAUDE.md forbids as firmly as inventing
# a number.
#
# Keys are (source, label as the source writes it).
CANONICAL_PROTOCOL: dict[tuple[str, str], str] = {
    # HumanEval's maintained leaderboard is EvalPlus, which publishes
    # GREEDY-DECODING PASS@1 and nothing else — this repo's own
    # benchmark-side fetcher reads exactly that column
    # (fetch_benchmark_scores.fetch_evalplus, and the committed
    # data/benchmark_scores/humaneval__evalplus.csv). Chen et al. (2021)
    # report pass@1/10/100, so the paper alone does not single one out;
    # the leaderboard does, and the leaderboard is what the catalog
    # already measures HumanEval's saturation from. Card metadata spells
    # it both "pass@1" and "Pass@1", so matching is case-insensitive.
    ("huggingface_hub_card", "HumanEval"): "pass@1",
}

# Labels with repeated entries for which NO canonical protocol could be
# sourced, with what is missing. Every entry in these groups is shown
# unweighted; none is averaged and none is picked.
#
# CURATE(you) on each, because each needs a source this repo does not
# have rather than a decision it can make:
NO_CANONICAL_PROTOCOL: dict[tuple[str, str], str] = {
    ("epoch_ai", "Aider polyglot"): (
        "CURATE(you): Aider's leaderboard reports each model with the edit "
        "format it was run under (Epoch's export carries the 'Edit format' "
        "column: diff 53, whole 16, diff-fenced 5, architect 3 of 77 rows). "
        "That is a per-model record, not a canonical protocol — and where a "
        "model has TWO formats reported the leaderboard gives no rule "
        "picking one. Qwen2.5-Coder-32B-Instruct scores 8.0 with `diff` and "
        "16.4 with `whole`. What would settle it: a statement from the "
        "leaderboard that one format is the headline number."
    ),
    ("epoch_ai", "Terminal Bench"): (
        "CURATE(you): the distinguishing column is 'Agent' — the scaffold "
        "driving the model, not a setting of the model. 44 of 60 model "
        "versions in the committed export carry several, and one model "
        "spans 0.580 to 0.798 across eleven agents. Terminal Bench does not "
        "designate a reference agent, so there is nothing to pick. What "
        "would settle it: a reference scaffold named by the benchmark."
    ),
    ("huggingface_hub_card", "MultiPL HumanEval (Python)"): (
        "CURATE(you): metric_name separates pass@1/pass@10/pass@100, but "
        "SIX pass@1 entries remain for bigcode/gpt_bigcode-santacoder "
        "(0.15, 0.16, 0.18, 0.28, 0.28, 0.35) with nothing to tell them "
        "apart. The Hub's model-index schema carries dataset.config and "
        "dataset.split, which would; fetch_models._extract_eval_results "
        "DROPS both. Fixed there as of 2026-09-23, but the committed "
        "data/models_raw.json predates the fix and a re-fetch is needed "
        "before it helps."
    ),
}


def _weighted_point(
    value: float,
    label: Optional[str],
    source: str,
    benchmark_trust: dict[str, BenchmarkTrust],
    config: Optional[str] = None,
) -> _DataPoint:
    """Attach benchmark trust to a normalized score."""
    benchmark = find_benchmark(label)
    if benchmark is not None and benchmark.key in benchmark_trust:
        trust = benchmark_trust[benchmark.key]
        return _DataPoint(
            value=value,
            benchmark_label=trust.benchmark.name,
            benchmark_key=benchmark.key,
            # HEALTH, not relevance. A model's HumanEval result counts
            # for less because HumanEval is a weak MEASUREMENT, not
            # because HumanEval is a poor match for the user's task —
            # the task match was already applied when the category was
            # chosen, and applying it twice was the bug the score split
            # was adopted to fix.
            benchmark_trust=trust.health,
            unweighted=trust.evidence_tier == "thin",
            source=source,
            config=config,
        )
    return _DataPoint(
        value=value,
        benchmark_label=str(label) if label else "unidentified benchmark",
        benchmark_key=None,
        # Unassessed: displayed, never weighted. The 0.0 is not a
        # judgement that the benchmark is bad — `unweighted` is what
        # carries the meaning, and the UI shows the result regardless.
        benchmark_trust=0.0,
        unweighted=True,
        source=source,
        config=config,
    )


def _benchmark_weighted_mean(points: list[_DataPoint]) -> float:
    """
    Average the points, weighted by how much each benchmark is worth
    trusting. A 90% on a saturated benchmark counts for less than a 60%
    on one that still separates models.
    """
    total_weight = sum(point.weight for point in points)
    if total_weight <= 0:
        return sum(p.value for p in points) / len(points)
    return sum(point.value * point.weight for point in points) / total_weight


def _normalize_value(value: float, scale: str) -> Optional[float]:
    """
    Normalize a raw benchmark number to 0-1 given its reported scale.

    TODO(you): this only handles the common "0-100" / "0-1" cases.
    Some benchmarks (e.g. pass@k code-eval variants, ELO-style scores)
    need bespoke normalization — extend this when you hit one.
    """
    try:
        if scale == "0-100":
            return max(0.0, min(1.0, value / 100.0))
        if scale == "0-1":
            return max(0.0, min(1.0, value))
        # Unknown scale: best-effort guess based on magnitude.
        if value > 1.0:
            return max(0.0, min(1.0, value / 100.0))
        return max(0.0, min(1.0, value))
    except (TypeError, ZeroDivisionError):
        return None


def _parse_card_value(value: Any) -> tuple[Optional[float], Optional[str]]:
    """
    Model-card metric values are free-form YAML, so they can be numbers
    or strings like "45.2" / "7.84%". Returns (number, scale), where scale
    is "0-100" for percent strings and None when it has to be guessed.
    """
    if isinstance(value, bool):
        return None, None
    if isinstance(value, (int, float)):
        return float(value), None
    if isinstance(value, str):
        text = value.strip()
        is_percent = text.endswith("%")
        try:
            number = float(text.rstrip("%").strip())
        except ValueError:
            return None, None
        return number, "0-100" if is_percent else None
    return None, None


def _days_since(date_str: Optional[str]) -> Optional[float]:
    if not date_str:
        return None
    try:
        # Accepts "2025-01-10", "2025-01-12T02:03:41+00:00", with or without
        # microseconds. fromisoformat() on Python < 3.11 rejects a trailing "Z".
        parsed = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - parsed).days


def _recency_factor(age_days: Optional[float]) -> float:
    """
    Exponential decay: 1.0 for a brand-new benchmark, 0.5 at the
    configured half-life, approaching 0 for very stale results.
    Unknown age is treated as moderately stale (0.5) rather than
    penalized to zero, since "unknown" isn't necessarily "old".
    """
    if age_days is None:
        return 0.5
    if age_days <= 0:
        return 1.0
    return 0.5 ** (age_days / STALENESS_HALF_LIFE_DAYS)


def _source_count_factor(num_sources: int) -> float:
    return SOURCE_COUNT_WEIGHTS.get(num_sources, SOURCE_COUNT_WEIGHTS_DEFAULT if num_sources >= 3 else 0.4)


def compute_trust_score(
    num_independent_sources: int,
    ages_days: list[float],
    self_reported_only: bool,
) -> float:
    """
    Combine source-count confidence with recency into one 0-1 trust
    multiplier, then penalize models whose only numbers are self-reported
    on their own model card.

    TODO(you): consider making this per-benchmark rather than one
    blended trust score per model, once you have enough real data
    points to justify the extra complexity.
    """
    source_factor = _source_count_factor(num_independent_sources)
    avg_age = sum(ages_days) / len(ages_days) if ages_days else None
    recency = _recency_factor(avg_age)
    trust = source_factor * recency
    if self_reported_only:
        trust *= SELF_REPORT_PENALTY
    return round(max(0.0, min(1.0, trust)), 4)


def score_model(
    raw_model: dict[str, Any],
    external_scores: Optional[list[ExternalScore]] = None,
    benchmark_trust: Optional[dict[str, BenchmarkTrust]] = None,
) -> ScoredModel:
    """
    Score a single model. `raw_model` is one entry from
    fetch_models.RawModel (as a dict). `external_scores` comes from
    ExternalScoreIndex.lookup(); an empty list means no external source
    covers this model, which the trust score penalizes.

    Data points are weighted by the trust of the benchmark they came
    from, so a result on a saturated benchmark moves the score less than
    one on a benchmark that still discriminates. `benchmark_trust` is
    passed in per batch; it's the same for every model.
    """
    external_scores = external_scores or []
    benchmark_trust = benchmark_trust if benchmark_trust is not None else trust_by_key()

    points: list[_DataPoint] = []
    ages_days: list[float] = []
    sources_seen: set[str] = set()

    # 1. Points from the Hub card's model-index eval_results.
    for point in raw_model.get("eval_results", []):
        value, scale = _parse_card_value(point.get("metric_value"))
        if value is None:
            continue
        norm = _normalize_value(value, scale or ("0-100" if value > 1 else "0-1"))
        if norm is not None:
            label = point.get("dataset") or point.get("metric_name")
            points.append(
                _weighted_point(
                    norm, label, HUB_CARD_SOURCE, benchmark_trust,
                    config=point.get("metric_name"),
                )
            )
            sources_seen.add(HUB_CARD_SOURCE)
            age = _days_since(raw_model.get("last_modified"))
            if age is not None:
                ages_days.append(age)

    # 2. Points from external sources (Artificial Analysis, Epoch AI, ...).
    for ext in external_scores:
        if ext.score is None:
            continue
        norm = _normalize_value(ext.score, ext.score_scale)
        if norm is not None:
            points.append(
                _weighted_point(
                    norm, ext.benchmark_name, ext.source, benchmark_trust,
                    config=ext.config,
                )
            )
            sources_seen.add(ext.source)
            age = _days_since(ext.reported_date)
            if age is not None:
                ages_days.append(age)

    self_reported_only = sources_seen == {HUB_CARD_SOURCE}
    normalized_points = [p.value for p in points]

    if not normalized_points:
        return ScoredModel(
            model_id=raw_model["model_id"],
            params_billion=raw_model.get("params_billion"),
            license=raw_model.get("license"),
            downloads=raw_model.get("downloads", 0),
            raw_benchmark_score=None,
            trust_score=None,
            composite_score=None,
            num_sources=0,
            benchmark_points_used=0,
            self_reported_only=False,
            provenance_verified=raw_model.get("provenance_verified", True),
            sources=[],
            benchmark_breakdown=[],
        )

    # SILENT AVERAGING IS OVER (D5, owner decision 2026-09-23). The same
    # source often reports one benchmark label several times, and those
    # entries used to be averaged with nothing saying so. The repeats are
    # NOT disagreement — they are incomparable configurations collapsed
    # under one label:
    #
    #   Hub cards  different metric_name under one dataset. pass@100
    #              exceeds pass@1 BY CONSTRUCTION, so their mean is over
    #              different quantities, not repeated measurements.
    #   Epoch      a distinguishing column: "Agent" (the scaffold),
    #              "Edit format", "Shots". Qwen2.5-Coder-32B-Instruct
    #              scores 8.0 with `diff` and 16.4 with `whole`.
    #
    # OPTION (iii), as decided: weight the entry matching the benchmark's
    # OWN canonical protocol, sourced from its paper or its official
    # leaderboard. Where no canonical protocol is documented, weight
    # NOTHING — every entry is shown as unweighted evidence with its
    # configuration named and a CURATE note. Picking one unsourced would
    # be inventing a protocol.
    groups: dict[tuple[str, str], list[_DataPoint]] = {}
    for point in points:
        groups.setdefault((point.benchmark_label, point.source), []).append(point)

    for (label, source), members in groups.items():
        if len(members) < 2:
            continue

        # EXACT DUPLICATES FIRST. Same configuration, same value, is one
        # measurement reported twice — a row duplicated in the source,
        # not two incomparable runs. Deduplicate rather than average:
        # averaging identical numbers is harmless arithmetically, but it
        # inflates benchmark_points_used and makes one datum look like
        # corroboration.
        seen: set[tuple[Optional[str], float]] = set()
        duplicates = []
        for point in members:
            signature = (point.config, round(point.value, 6))
            if signature in seen:
                duplicates.append(point)
            seen.add(signature)
        for point in duplicates:
            point.unweighted = True
            point.unweighted_reason = "exact duplicate of another entry from this source"
        remaining = [p for p in members if p not in duplicates]
        if len(remaining) < 2:
            continue

        canonical = CANONICAL_PROTOCOL.get((source, label))
        if canonical is not None:
            matching = [
                p for p in remaining
                if (p.config or "").strip().lower() == canonical.lower()
            ]
            if len(matching) == 1:
                for point in remaining:
                    if point is not matching[0]:
                        point.unweighted = True
                        point.unweighted_reason = (
                            f"{point.config or 'configuration not recorded'} — "
                            f"the canonical protocol for {label} is {canonical}"
                        )
                continue
            # The canonical protocol is documented but does not resolve
            # this group — zero matches, or several. Falls through to the
            # no-canonical treatment rather than guessing between them.

        reason = NO_CANONICAL_PROTOCOL.get(
            (source, label),
            f"CURATE(you): {source} reports {label} {len(remaining)} times for "
            "this model and no canonical protocol is recorded for it. "
            "Nothing is averaged and nothing is picked.",
        )
        for point in remaining:
            point.unweighted = True
            point.unweighted_reason = reason

    repeats: dict[tuple[str, str], list[float]] = {}
    for point in points:
        repeats.setdefault((point.benchmark_label, point.source), []).append(point.value)

    def _repeat_note(point: _DataPoint) -> Optional[dict[str, Any]]:
        values = repeats[(point.benchmark_label, point.source)]
        if len(values) < 2:
            return None
        return {
            "entries": len(values),
            "spread": round(max(values) - min(values), 4),
            "values": sorted(round(v, 4) for v in values),
        }

    raw_benchmark_score = _benchmark_weighted_mean(points)
    trust_score = compute_trust_score(len(sources_seen), ages_days, self_reported_only)
    composite_score = round(raw_benchmark_score * trust_score, 4)

    return ScoredModel(
        model_id=raw_model["model_id"],
        params_billion=raw_model.get("params_billion"),
        license=raw_model.get("license"),
        downloads=raw_model.get("downloads", 0),
        raw_benchmark_score=round(raw_benchmark_score, 4),
        trust_score=trust_score,
        composite_score=composite_score,
        num_sources=len(sources_seen),
        benchmark_points_used=len(normalized_points),
        self_reported_only=self_reported_only,
        provenance_verified=raw_model.get("provenance_verified", True),
        sources=sorted(sources_seen),
        sources_agree=_sources_agree(points),
        has_weighted_evidence=any(p.weight > 0 for p in points),
        benchmark_breakdown=[
            {
                "benchmark": point.benchmark_label,
                "trust": round(point.benchmark_trust, 1),
                "score": round(point.value, 4),
                "source": point.source,
                "recognized": point.benchmark_key is not None,
                # Shown beside the score rather than folded into it.
                "unweighted": point.unweighted,
                # Which configuration produced this number, and — when the
                # D5 rule is what unweighted it — why it carries no weight.
                "config": point.config,
                "unweighted_reason": point.unweighted_reason,
                # A published aggregate over other benchmarks, not a
                # benchmark. Listed so a reader can see what it contains.
                "composite_of": COMPOSITE_COMPONENTS.get(point.benchmark_label),
                # None unless this source reported this label more than
                # once; then the group's size, spread and values.
                "repeated": _repeat_note(point),
            }
            for point in sorted(points, key=lambda p: p.benchmark_trust, reverse=True)
        ],
    )


def _sources_agree(points: list[_DataPoint]) -> Optional[bool]:
    """
    Do independent sources reporting the same benchmark for this model
    agree, within the tolerance the benchmark side already uses?

    REUSES `cross_source.SCATTER_TOLERANCE` deliberately. A second
    threshold for the same idea would be a duplicate with its own
    unsourced constant, and this project has enough of those. The
    benchmark side asks the same question about a benchmark's evaluators;
    this asks it about a model's reporters.

    Returns None when nothing is comparable — which is EVERY case today.

    MEASURED 2026-09-22, correcting an earlier count in
    docs/MODEL_SIDE_AUDIT.md: of 81 scored models, **none** has two
    different sources reporting the same benchmark. The earlier "one
    pair, spread 0.022" was a miscount — those were two `epoch_ai`
    entries, not two sources. So this rung fires on zero models and is
    purely a guard.

    WHAT THE MISCOUNT UNCOVERED, which is a larger problem: the same
    source frequently reports the same benchmark label several times.
    `bigcode/gpt_bigcode-santacoder` carries **20** entries under
    "MultiPL HumanEval (Python)" ranging 0.15 to 0.77 — different
    languages and pass@k values collapsed under one label — and all of
    them are averaged into its score. Grouping by source here
    deliberately keeps only one value per source, so within-source
    multiplicity is NOT treated as disagreement. It is a separate defect
    of `raw_benchmark_score`, recorded in the audit.
    """
    from cross_source import SCATTER_TOLERANCE

    by_benchmark: dict[str, dict[str, float]] = {}
    for point in points:
        by_benchmark.setdefault(point.benchmark_label, {})[point.source] = point.value

    spreads = [
        max(values.values()) - min(values.values())
        for values in by_benchmark.values()
        if len(values) > 1
    ]
    if not spreads:
        return None
    return max(spreads) <= SCATTER_TOLERANCE


def score_models(
    raw_models: list[dict[str, Any]],
    index: Optional[ExternalScoreIndex] = None,
    benchmark_trust: Optional[dict[str, BenchmarkTrust]] = None,
) -> list[ScoredModel]:
    """
    Score a batch of models, ranked descending by composite_score.

    External sources and benchmark trust scores are computed once for the
    whole batch: the sources are bulk catalogs (Artificial Analysis' free
    tier allows fewer requests per day than we have models), and trust is
    a property of the benchmark, not of any model.
    """
    if index is None:
        index = build_external_index()
    if benchmark_trust is None:
        benchmark_trust = trust_by_key()
    scored = [
        score_model(m, index.lookup(m["model_id"]), benchmark_trust) for m in raw_models
    ]
    scored.sort(key=rank_key, reverse=True)
    return scored


def rank_key(model: ScoredModel) -> tuple[bool, bool, bool, bool, int, float]:
    """
    Tier before comparing composite scores:

      1. has any benchmark data at all
      2. the repo is confirmed to hold the weights that were benchmarked
      3. an independent source reported it, not just the model's own card

    The trust multiplier alone can't express this. A model that scores
    itself 95 on its own card still outranks an independently-measured
    competitor once multiplied, and a score attributed to an unconfirmed
    repo may belong to a different model entirely — no penalty factor
    makes that comparable. Tiering says what we actually mean without
    tuning constants until the ordering happens to look right.
    """
    has_score = model.composite_score is not None
    # Agreement is a rung on the same ladder, added 2026-09-22:
    #   2  checked and agreeing
    #   1  nothing comparable to check
    #   0  checked and contradicting
    # Unchecked sits BETWEEN the two on purpose. It must not outrank
    # demonstrated agreement — that would be the uncheckability bug this
    # project has now found five times — and it should not be treated as
    # badly as a demonstrated contradiction.
    agreement_rank = {True: 2, None: 1, False: 0}[model.sources_agree]
    return (
        has_score,
        model.provenance_verified,
        has_score and not model.self_reported_only,
        # BELOW provenance and self-reporting, deliberately. An earlier
        # draft put weighted evidence above them, which let a
        # self-reported number on a catalogued benchmark outrank an
        # independently corroborated one on an unassessed benchmark —
        # inverting this module's founding rule that an unverified
        # number is not evidence. Weighting separates models WITHIN the
        # verified-and-corroborated group; it does not outrank
        # verification itself.
        model.has_weighted_evidence,
        agreement_rank,
        model.composite_score or 0.0,
    )


if __name__ == "__main__":
    # Quick manual smoke test with a fabricated raw model.
    fake_model = {
        "model_id": "example-org/example-coder-7b",
        "params_billion": 7.0,
        "license": "apache-2.0",
        "eval_results": [{"metric_name": "pass@1", "metric_value": 45.2}],
        "downloads": 12345,
        "last_modified": "2025-01-10",
    }
    result = score_model(fake_model)
    print(result)
