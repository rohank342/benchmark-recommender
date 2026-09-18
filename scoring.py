"""
scoring.py
==========
Turns raw benchmark numbers (from the Hub card + enrich_scores.py's
external sources) into one composite, rankable score per model.

Pipeline:
  1. Collect every benchmark data point available for a model (Hub
     card `model-index` results + Artificial Analysis + Epoch AI).
  2. Normalize each to a 0-1 scale.
  3. Average them into a raw benchmark score (0-1).
  4. Apply a "trust discount" — a 0-1 multiplier that penalizes scores
     backed by few independent sources, that are stale, or that are only
     self-reported on the model's own card.
  5. composite_score = raw_benchmark_score * trust_score

This is intentionally simple for v1. The TODOs below mark the spots
that most deserve real thought later (per-benchmark weighting, decay
curve tuning, etc.).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from enrich_scores import ExternalScore, ExternalScoreIndex, build_external_index

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
    sources: list[str] = field(default_factory=list)


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


def score_model(raw_model: dict[str, Any], external_scores: Optional[list[ExternalScore]] = None) -> ScoredModel:
    """
    Score a single model. `raw_model` is one entry from
    fetch_models.RawModel (as a dict). `external_scores` comes from
    ExternalScoreIndex.lookup(); an empty list means no external source
    covers this model, which the trust score penalizes.
    """
    external_scores = external_scores or []

    normalized_points: list[float] = []
    ages_days: list[float] = []
    sources_seen: set[str] = set()

    # 1. Points from the Hub card's model-index eval_results.
    for point in raw_model.get("eval_results", []):
        value, scale = _parse_card_value(point.get("metric_value"))
        if value is None:
            continue
        norm = _normalize_value(value, scale or ("0-100" if value > 1 else "0-1"))
        if norm is not None:
            normalized_points.append(norm)
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
            normalized_points.append(norm)
            sources_seen.add(ext.source)
            age = _days_since(ext.reported_date)
            if age is not None:
                ages_days.append(age)

    self_reported_only = sources_seen == {HUB_CARD_SOURCE}

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
            sources=[],
        )

    raw_benchmark_score = sum(normalized_points) / len(normalized_points)
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
        sources=sorted(sources_seen),
    )


def score_models(
    raw_models: list[dict[str, Any]], index: Optional[ExternalScoreIndex] = None
) -> list[ScoredModel]:
    """
    Score a batch of models, ranked descending by composite_score.

    External sources are loaded once for the whole batch — they are bulk
    catalogs, and Artificial Analysis' free tier allows fewer requests
    per day than we have models to score.
    """
    if index is None:
        index = build_external_index()
    scored = [score_model(m, index.lookup(m["model_id"])) for m in raw_models]
    scored.sort(key=rank_key, reverse=True)
    return scored


def rank_key(model: ScoredModel) -> tuple[bool, bool, float]:
    """
    Rank corroborated models above self-reported ones, and both above
    models with no benchmark data, before comparing composite scores.

    The trust multiplier alone can't express this: a model that scores
    itself 95 on its own card still outranks an independently-measured
    competitor once multiplied. Tiering says the thing we actually mean —
    an unverified number is not evidence — without tuning a penalty until
    the ordering happens to look right.
    """
    has_score = model.composite_score is not None
    return (
        has_score,
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
