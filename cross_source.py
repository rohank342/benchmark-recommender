"""
cross_source.py
===============
Do independent evaluators agree about the same models on the same
benchmark?

This is the reproducibility question, measured rather than proxied. The
catalog's `independent_evaluators` count says how many groups publish
scores; it says nothing about whether those scores match. A benchmark
two labs both report but disagree about by fifteen points is worse than
one lab reporting carefully, and counting can't see that.

Method: find models appearing in two sources for the same benchmark,
match them by name (model_matching handles the naming chaos), and look
at the distribution of per-model differences. Two components come out of
it, and they mean different things:

  offset   The median signed difference. A systematic gap — one source
           consistently scores higher — is a methodology difference:
           different shot counts, harnesses, or prompt formats. It says
           a published number isn't meaningful without knowing who ran it.
  scatter  The spread of differences after removing the offset. This is
           irreproducibility proper: the same model, the same benchmark,
           two credible evaluators, answers that don't line up.

The reproducibility factor is built from scatter. Offset is reported
separately rather than folded in, because a constant gap is a fact about
the two harnesses while scatter is a fact about the benchmark.

########################################################################
# Comparability is the whole problem here, and getting it wrong produces
# confident nonsense. Two guards:
#
#   1. Normalization must match. The HF v2 leaderboard publishes
#      baseline-rescaled scores alongside raw ones, and v1 reported ARC
#      and HellaSwag as length-normalized accuracy. Comparing a
#      normalized column against a raw one measures the normalization:
#      before this was enforced, GPQA's median delta read 24.5 points.
#      With raw columns on both sides it is 7.9.
#   2. Enough overlapping models. Below MIN_OVERLAP the median is noise.
#
# Failing either, the deltas are returned as diagnostics and the caller
# falls back to the curated evaluator count. Reporting "unmeasurable" is
# the honest output; a number computed across incomparable sources is not.
########################################################################
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Optional

from fetch_benchmarks import Benchmark, BenchmarkScores, load_score_sets
from model_matching import match_key

# Which normalizations are on the SAME SCALE and can therefore be
# compared model-for-model, with their difference reported as an offset.
#
# FIXED 2026-09-22. The guard used to refuse any comparison where the two
# normalizations differed at all, which conflated two different problems:
#
#   "none" vs "length" — BOTH are accuracy in 0-1. acc_norm reweights by
#       answer length, so it is a different quantity, but it is the same
#       KIND of quantity on the same scale. The offset/scatter split
#       exists precisely to handle a systematic difference like this:
#       report the offset, measure the scatter.
#   "none" vs "baseline" — NOT the same scale. v2's rescale maps chance
#       to 0, so GPQA's raw 0.26 becomes 1.2. Comparing that against a
#       raw column measures the rescaling; it is what made GPQA's median
#       delta read 24.5 points when the truth was 7.9.
#
# Refusing the first cost more than it saved: ARC and HellaSwag both had
# a comparison that was possible, and the refusal fell through to the
# curated evaluator count, which paid them the MAXIMUM 1.000. Being
# uncheckable was worth more than being checked.
#
# CAVEAT, and it is a real one: length normalization is a per-item
# reweighting rather than a constant shift, so some of the scatter it
# produces is the normalization itself. Reproducibility measured across
# a length/none pair is a LOWER BOUND on the true value, not an
# estimate. That is still far better than 1.000.
NORMALIZATION_SCALE = {
    "none": "accuracy",
    "length": "accuracy",
    "baseline": "chance-rescaled",
}

# Fewer shared models than this and the median difference is noise.
MIN_OVERLAP = 10

# Scatter (in score points, 0-1) at which reproducibility scores zero.
# 0.08 = eight points of unexplained disagreement on the same model,
# which is more than the gap between many neighbouring leaderboard rows.
# TODO(you): a judgement call, not a fitted value.
SCATTER_TOLERANCE = 0.08

# Systematic offset above which the sources are reported as measuring
# under materially different conditions.
LARGE_OFFSET = 0.05


@dataclass
class AgreementReport:
    """What two sources say about the same models on one benchmark."""

    benchmark_key: str
    source_a: str
    source_b: str
    overlap: int
    offset: Optional[float] = None  # median signed delta (a - b)
    scatter: Optional[float] = None  # median |delta - offset|
    comparable: bool = False
    reason: str = ""
    worst: list[tuple[str, float, float]] = field(default_factory=list)

    @property
    def systematic(self) -> bool:
        return self.offset is not None and abs(self.offset) > LARGE_OFFSET

    def describe(self) -> str:
        if not self.comparable:
            return f"not comparable: {self.reason}"
        line = (
            f"{self.overlap} models scored by both {self.source_a} and "
            f"{self.source_b}; unexplained scatter {self.scatter * 100:.1f} points"
        )
        if self.systematic:
            line += (
                f", plus a systematic {self.offset * 100:+.1f}-point gap between the "
                "two harnesses — a published score on this benchmark is not "
                "meaningful without knowing who produced it"
            )
        return line


def _index_by_model(scores: BenchmarkScores) -> dict[str, float]:
    """Mean score per matched model name."""
    grouped: dict[str, list[float]] = {}
    for name, score in zip(scores.model_names, scores.scores):
        key = match_key(name)
        if key:
            grouped.setdefault(key, []).append(score)
    return {key: statistics.mean(values) for key, values in grouped.items()}


def compare_sources(a: BenchmarkScores, b: BenchmarkScores) -> AgreementReport:
    """Compare two score sets for the same benchmark, model by model."""
    report = AgreementReport(
        benchmark_key=a.benchmark_key, source_a=a.source, source_b=b.source, overlap=0
    )

    if NORMALIZATION_SCALE.get(a.normalization) != NORMALIZATION_SCALE.get(
        b.normalization
    ):
        report.reason = (
            f"{a.source} reports {a.normalization or 'none'}-normalized scores and "
            f"{b.source} reports {b.normalization or 'none'} — different scales"
        )
        return report

    index_a, index_b = _index_by_model(a), _index_by_model(b)
    shared = sorted(set(index_a) & set(index_b))
    report.overlap = len(shared)
    if len(shared) < MIN_OVERLAP:
        report.reason = f"only {len(shared)} shared models, need {MIN_OVERLAP}"
        return report

    deltas = [(key, index_a[key] - index_b[key]) for key in shared]
    offset = statistics.median(delta for _, delta in deltas)
    scatter = statistics.median(abs(delta - offset) for _, delta in deltas)

    report.offset = offset
    report.scatter = scatter
    report.comparable = True
    report.worst = sorted(
        ((key, index_a[key], index_b[key]) for key, _ in deltas),
        key=lambda row: -abs(row[1] - row[2]),
    )[:5]
    return report


@lru_cache(maxsize=None)
def _agreement_by_key(key: str) -> Optional[AgreementReport]:
    from fetch_benchmarks import find_benchmark

    benchmark = find_benchmark(key)
    if benchmark is None:
        return None
    sets = sorted(load_score_sets(benchmark), key=lambda s: -len(s.scores))
    if len(sets) < 2:
        return None
    return compare_sources(sets[0], sets[1])


def agreement_for(benchmark: Benchmark) -> Optional[AgreementReport]:
    """
    Cross-source agreement for one benchmark, or None when only one
    source covers it.

    With more than two sources this compares the two largest; a full
    pairwise treatment would need a way to combine disagreements that
    doesn't hide a single bad source among several good ones.
    """
    return _agreement_by_key(benchmark.key)


def reproducibility_from_agreement(report: AgreementReport) -> Optional[float]:
    """0-1 reproducibility from measured scatter, or None if unusable."""
    if not report.comparable or report.scatter is None:
        return None
    return max(0.0, 1.0 - min(report.scatter / SCATTER_TOLERANCE, 1.0))


if __name__ == "__main__":
    from fetch_benchmarks import load_benchmark_catalog

    print(f"{'benchmark':<26}{'overlap':>8}{'offset':>9}{'scatter':>9}{'repro':>7}  status")
    print("-" * 104)
    for benchmark in load_benchmark_catalog():
        report = agreement_for(benchmark)
        if report is None:
            continue
        value = reproducibility_from_agreement(report)
        offset = f"{report.offset * 100:+.1f}" if report.offset is not None else "  —"
        scatter = f"{report.scatter * 100:.1f}" if report.scatter is not None else "  —"
        repro = f"{value:.2f}" if value is not None else "  —"
        status = "comparable" if report.comparable else report.reason
        if report.comparable and report.systematic:
            status = "comparable, systematic gap"
        print(
            f"{benchmark.name:<26}{report.overlap:>8}{offset:>9}{scatter:>9}{repro:>7}  {status}"
        )
