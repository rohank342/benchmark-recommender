import pytest

from cross_source import (
    MIN_OVERLAP,
    SCATTER_TOLERANCE,
    agreement_for,
    compare_sources,
    reproducibility_from_agreement,
)
from fetch_benchmarks import BenchmarkScores, find_benchmark


def _set(source, pairs, normalization="none"):
    return BenchmarkScores(
        benchmark_key="test",
        scores=[score for _, score in pairs],
        model_names=[name for name, _ in pairs],
        source=source,
        normalization=normalization,
    )


def _models(n, base=0.5, step=0.01):
    return [(f"org/model-{i}b", base + i * step) for i in range(n)]


class TestComparability:
    def test_mismatched_normalization_is_refused(self):
        """The bug this guard exists for: raw vs baseline-normalized."""
        a = _set("epoch_ai", _models(30), normalization="none")
        b = _set("hf", _models(30), normalization="baseline")
        report = compare_sources(a, b)
        assert not report.comparable
        assert "different scales" in report.reason
        assert reproducibility_from_agreement(report) is None

    def test_length_normalized_is_now_comparable(self):
        """
        Changed 2026-09-22. acc_norm and raw accuracy are both accuracy
        in 0-1 — a different quantity on the SAME scale, which is
        exactly what the offset/scatter split handles. Refusing it fell
        through to the curated count, which paid the maximum.
        """
        a = _set("epoch_ai", _models(30), normalization="none")
        b = _set("hf", _models(30), normalization="length")
        assert compare_sources(a, b).comparable

    def test_too_few_shared_models_is_refused(self):
        a = _set("epoch_ai", _models(MIN_OVERLAP - 1))
        b = _set("hf", _models(MIN_OVERLAP - 1))
        report = compare_sources(a, b)
        assert not report.comparable
        assert "shared models" in report.reason

    def test_disjoint_model_sets_have_no_overlap(self):
        a = _set("epoch_ai", [(f"org/alpha-{i}b", 0.5) for i in range(20)])
        b = _set("hf", [(f"org/beta-{i}b", 0.5) for i in range(20)])
        report = compare_sources(a, b)
        assert report.overlap == 0
        assert not report.comparable


class TestAgreementMeasurement:
    def test_identical_sources_agree_perfectly(self):
        pairs = _models(30)
        report = compare_sources(_set("a", pairs), _set("b", pairs))
        assert report.comparable
        assert report.scatter == pytest.approx(0.0)
        assert reproducibility_from_agreement(report) == pytest.approx(1.0)

    def test_constant_offset_is_not_counted_as_scatter(self):
        """A systematic gap is a harness difference, not irreproducibility."""
        pairs = _models(30)
        shifted = [(name, score + 0.10) for name, score in pairs]
        report = compare_sources(_set("a", shifted), _set("b", pairs))
        assert report.offset == pytest.approx(0.10, abs=1e-6)
        assert report.scatter == pytest.approx(0.0, abs=1e-6)
        assert report.systematic
        assert "systematic" in report.describe()
        # Scatter drives the factor, so a pure offset still scores well.
        assert reproducibility_from_agreement(report) == pytest.approx(1.0)

    def test_scatter_lowers_the_score(self):
        pairs = _models(30)
        noisy = [
            (name, score + (0.09 if i % 2 else -0.09))
            for i, (name, score) in enumerate(pairs)
        ]
        report = compare_sources(_set("a", noisy), _set("b", pairs))
        assert report.scatter > SCATTER_TOLERANCE
        assert reproducibility_from_agreement(report) == pytest.approx(0.0)

    def test_model_name_variants_still_match(self):
        """Sources name models differently; that's model_matching's job."""
        a = _set("epoch_ai", [("Qwen2.5 Coder Instruct 7B", 0.50)] + _models(15))
        b = _set("hf", [("Qwen/Qwen2.5-Coder-7B-Instruct", 0.50)] + _models(15))
        assert compare_sources(a, b).overlap == 16


class TestRealCatalog:
    def test_mmlu_sources_agree_closely(self):
        """Two evaluators, 48 shared models, under a point of scatter."""
        report = agreement_for(find_benchmark("MMLU"))
        assert report.comparable
        assert report.overlap > 40
        assert report.scatter < 0.02
        assert reproducibility_from_agreement(report) > 0.8

    def test_gpqa_sources_disagree_substantially(self):
        """
        The finding: GPQA Diamond has several evaluators but they do not
        agree about the same models. 198 questions means one item is half
        a point, so eight points of scatter is a lot of items.
        """
        report = agreement_for(find_benchmark("GPQA Diamond"))
        assert report.comparable
        assert report.scatter > 0.05
        assert reproducibility_from_agreement(report) < 0.2

    def test_length_normalized_benchmarks_are_now_measured(self):
        """ARC and HellaSwag: acc_norm vs raw is same-scale, so comparable."""
        for name in ("ARC (AI2 Reasoning Challenge)", "HellaSwag"):
            report = agreement_for(find_benchmark(name))
            assert report.comparable, name
            assert report.overlap >= 10, name

    def test_single_source_benchmarks_have_no_report(self):
        assert agreement_for(find_benchmark("SWE-Bench Verified")) is None
        assert agreement_for(find_benchmark("LiveCodeBench")) is None


class TestFactorIntegration:
    def test_measured_where_possible_curated_otherwise(self):
        from benchmark_scoring import score_benchmark

        measured = {f.name: f for f in score_benchmark(find_benchmark("MMLU")).factors}
        assert measured["reproducibility"].basis == "measured"
        assert "scored by both" in measured["reproducibility"].explanation

        # TruthfulQA has one source, so there is nothing to compare.
        curated = {f.name: f for f in score_benchmark(find_benchmark("TruthfulQA")).factors}
        assert curated["reproducibility"].basis == "curated"

    def test_single_source_benchmark_uses_the_count_silently(self):
        from benchmark_scoring import score_benchmark

        factors = {f.name: f for f in score_benchmark(find_benchmark("MirrorCode")).factors}
        assert factors["reproducibility"].basis == "curated"
        assert "cross-source check unavailable" not in factors["reproducibility"].explanation

    def test_measurement_can_contradict_the_count(self):
        """GPQA: 5 curated evaluators, near-zero measured agreement."""
        from benchmark_scoring import score_benchmark

        gpqa = find_benchmark("GPQA Diamond")
        assert gpqa.independent_evaluators >= 5  # the proxy says "well covered"
        factor = {f.name: f for f in score_benchmark(gpqa).factors}["reproducibility"]
        assert factor.basis == "measured"
        assert factor.value < 0.2  # the measurement disagrees


class TestNormalizationScaleGuard:
    """
    Fixed 2026-09-22. The guard refused any normalization mismatch, which
    paid ARC and HellaSwag the maximum 1.000 for being uncheckable.
    """

    def test_same_scale_different_normalization_is_now_comparable(self):
        from cross_source import agreement_for
        from fetch_benchmarks import find_benchmark

        for name in ("ARC (AI2 Reasoning Challenge)", "HellaSwag"):
            report = agreement_for(find_benchmark(name))
            assert report is not None and report.comparable, name
            assert report.overlap >= 10, name

    def test_a_different_scale_is_still_refused(self):
        """v2's chance-rescaling is not accuracy and must stay refused."""
        from dataclasses import replace

        from cross_source import compare_sources
        from fetch_benchmarks import find_benchmark, load_score_sets

        a, b = load_score_sets(find_benchmark("ARC (AI2 Reasoning Challenge)"))[:2]
        report = compare_sources(replace(a, normalization="baseline"), b)
        assert not report.comparable
        assert "different scales" in report.reason

    def test_being_uncheckable_no_longer_outscores_being_checked(self):
        """
        The bug in one assertion: ARC used to score 1.000 because its
        sources could not be compared. Measured, it is 0.620.
        """
        from benchmark_scoring import score_benchmark
        from fetch_benchmarks import find_benchmark

        arc = score_benchmark(find_benchmark("ARC (AI2 Reasoning Challenge)"))
        factor = {f.name: f for f in arc.factors}["reproducibility"]
        assert factor.basis == "measured"
        assert factor.value < 0.8
