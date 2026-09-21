import pytest

from benchmark_scoring import (
    LEAKAGE_HALF_LIFE_DAYS,
    measure_saturation,
    score_all_benchmarks,
    score_benchmark,
    trust_by_key,
)
from fetch_benchmarks import (
    Benchmark,
    BenchmarkScores,
    find_benchmark,
    load_benchmark_catalog,
    load_benchmark_scores,
)


def _scores(values, ceiling=1.0, baseline=0.0):
    return BenchmarkScores(
        benchmark_key="test", scores=list(values), ceiling=ceiling, random_baseline=baseline
    )


class TestSaturationMeasurement:
    def test_clustered_near_ceiling_is_saturated(self):
        """Everyone scoring 94-96%: the benchmark has stopped answering."""
        saturation, _ = measure_saturation(_scores([0.96, 0.95, 0.95, 0.94, 0.94] * 2))
        assert saturation > 0.85

    def test_wide_spread_is_discriminating(self):
        saturation, _ = measure_saturation(
            _scores([0.85, 0.70, 0.62, 0.55, 0.43, 0.38, 0.30, 0.22, 0.15, 0.08])
        )
        assert saturation < 0.35

    def test_clustered_at_the_bottom_also_fails_to_discriminate(self):
        """A benchmark everyone fails equally ranks models no better."""
        saturation, _ = measure_saturation(_scores([0.05, 0.04, 0.04, 0.03, 0.03] * 2))
        assert saturation > 0.5

    def test_explanation_reports_the_numbers(self):
        _, explanation = measure_saturation(_scores([0.9, 0.5] * 5))
        assert "%" in explanation and "top" in explanation

    def test_too_few_scores_is_not_a_confident_answer(self):
        saturation, explanation = measure_saturation(_scores([0.8]))
        assert saturation == 0.5
        assert "too few" in explanation


class TestTrustScore:
    def test_old_contaminated_benchmark_scores_low(self):
        """HellaSwag (2019, flagged) is the calibration case for 'do not trust'."""
        trust = score_benchmark(find_benchmark("HellaSwag"))
        assert trust.trust_score < 35
        assert "reported contamination" in trust.penalties

    def test_recent_task_specific_benchmark_scores_higher(self):
        swe = score_benchmark(find_benchmark("SWE-Bench Verified"))
        hellaswag = score_benchmark(find_benchmark("HellaSwag"))
        assert swe.trust_score > hellaswag.trust_score

    def test_humaneval_ranks_below_its_reputation(self):
        """The thesis in one assertion: fame and validity have come apart."""
        humaneval = score_benchmark(find_benchmark("HumanEval"))
        mirrorcode = score_benchmark(find_benchmark("MirrorCode"))
        assert humaneval.trust_score < mirrorcode.trust_score

    def test_breakdown_accounts_for_the_whole_score(self):
        trust = score_benchmark(find_benchmark("GPQA Diamond"))
        assert {f.name for f in trust.factors} == {
            "discrimination",
            "freshness",
            "reproducibility",
            "specificity",
        }
        # No penalties on this one, so contributions should sum to the score.
        assert not trust.penalties
        assert sum(f.contribution for f in trust.factors) == pytest.approx(
            trust.trust_score, abs=0.2
        )

    def test_measured_benchmarks_say_so(self):
        measured = score_benchmark(find_benchmark("MMLU"))
        curated = score_benchmark(find_benchmark("HumanEval"))
        assert measured.measured_saturation is not None
        assert measured.models_measured > 0
        assert curated.measured_saturation is None
        discrimination = {f.name: f for f in curated.factors}["discrimination"]
        assert discrimination.basis == "curated"

    def test_dominant_factor_is_the_weakest_one(self):
        trust = score_benchmark(find_benchmark("HellaSwag"))
        weakest = trust.dominant_factor
        assert all(weakest.value <= f.value for f in trust.factors)

    def test_freshness_halves_at_the_half_life(self):
        from datetime import date, timedelta

        recent = Benchmark(
            key="t1", name="T1", category="code generation",
            release_date=date.today().isoformat(), independent_evaluators=5,
        )
        older = Benchmark(
            key="t2", name="T2", category="code generation",
            release_date=(date.today() - timedelta(days=LEAKAGE_HALF_LIFE_DAYS)).isoformat(),
            independent_evaluators=5,
        )
        fresh = {f.name: f for f in score_benchmark(recent).factors}["freshness"]
        stale = {f.name: f for f in score_benchmark(older).factors}["freshness"]
        assert stale.value == pytest.approx(fresh.value / 2, rel=0.02)

    def test_scores_stay_in_range(self):
        for trust in score_all_benchmarks():
            assert 0.0 <= trust.trust_score <= 100.0


class TestCatalog:
    def test_every_entry_has_a_category_the_matcher_knows(self):
        from fetch_benchmarks import CATEGORIES

        for benchmark in load_benchmark_catalog():
            assert benchmark.category in CATEGORIES

    def test_aliases_resolve_to_the_same_benchmark(self):
        assert find_benchmark("SWE-bench Verified").key == "swe_bench_verified"
        assert find_benchmark("GPQA").key == "gpqa_diamond"
        assert find_benchmark("BBH").key == "bbh"
        assert find_benchmark("nonsense-benchmark") is None
        assert find_benchmark(None) is None

    def test_score_files_load_where_declared(self):
        for benchmark in load_benchmark_catalog():
            if benchmark.epoch_source_file:
                scores = load_benchmark_scores(benchmark)
                assert scores is not None, f"{benchmark.name} declares a file that didn't load"
                assert scores.scores

    def test_benchmarks_without_data_return_none_not_an_error(self):
        assert load_benchmark_scores(find_benchmark("HumanEval")) is None

    def test_trust_by_key_covers_the_catalog(self):
        by_key = trust_by_key()
        assert {b.key for b in load_benchmark_catalog()} == set(by_key)
