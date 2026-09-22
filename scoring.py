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

# Weight given to a data point whose benchmark isn't in the catalog —
# composite indices like Artificial Analysis' coding index, or a model
# card citing something unrecognized. Middling on purpose: an unknown
# benchmark is not evidence of a bad one, but it can't be trusted like a
# benchmark that has been assessed.
# TODO(you): shrink this as the catalog grows to cover what sources report.
#
# CHECKED 2026-09-22 for the score split and LEFT AT 45.0. The worry was
# that 45.0 was calibrated against the old combined scale; measuring
# both distributions shows they barely moved:
#
#   old combined:  mean 44.4, median 41.5, range 15.7-76.3
#   health only:   mean 43.0, median 43.5, range 14.6-72.9
#
# So 45.0 still sits just above the middle of the catalog, which is what
# it was chosen to do. Changing it would have been an unforced parameter
# change justified by nothing. It stays a placeholder rather than a
# measurement, which is why it is not derived from the distribution
# above — adding benchmarks must not quietly move it.
UNKNOWN_BENCHMARK_TRUST = 45.0

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

    @property
    def weight(self) -> float:
        if self.unweighted:
            return 0.0
        return self.benchmark_trust / 100.0


def _weighted_point(
    value: float,
    label: Optional[str],
    source: str,
    benchmark_trust: dict[str, BenchmarkTrust],
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
        )
    return _DataPoint(
        value=value,
        benchmark_label=str(label) if label else "unidentified benchmark",
        benchmark_key=None,
        benchmark_trust=UNKNOWN_BENCHMARK_TRUST,
        source=source,
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
            points.append(_weighted_point(norm, label, HUB_CARD_SOURCE, benchmark_trust))
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
            points.append(_weighted_point(norm, ext.benchmark_name, ext.source, benchmark_trust))
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
        benchmark_breakdown=[
            {
                "benchmark": point.benchmark_label,
                "trust": round(point.benchmark_trust, 1),
                "score": round(point.value, 4),
                "source": point.source,
                "recognized": point.benchmark_key is not None,
                # Shown beside the score rather than folded into it.
                "unweighted": point.unweighted,
            }
            for point in sorted(points, key=lambda p: p.benchmark_trust, reverse=True)
        ],
    )


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


def rank_key(model: ScoredModel) -> tuple[bool, bool, bool, float]:
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
    return (
        has_score,
        model.provenance_verified,
        has_score and not model.self_reported_only,
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
