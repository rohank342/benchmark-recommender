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
        # Its contamination has never been quantified, so since 2026-09-21
        # the flag warns rather than charges. The score stays low on the
        # measured factors, which is the point: it did not need the penalty.
        assert any(p.startswith("WARNING:") for p in trust.penalties), trust.penalties

    def test_recent_task_specific_benchmark_scores_higher(self):
        swe = score_benchmark(find_benchmark("SWE-Bench Verified"))
        hellaswag = score_benchmark(find_benchmark("HellaSwag"))
        assert swe.trust_score > hellaswag.trust_score

    def test_humaneval_ranks_below_its_reputation(self):
        """The thesis in one assertion: fame and validity have come apart."""
        humaneval = score_benchmark(find_benchmark("HumanEval"))
        mirrorcode = score_benchmark(find_benchmark("MirrorCode"))
        assert humaneval.trust_score < mirrorcode.trust_score

    def test_breakdown_accounts_for_the_whole_health_score(self):
        """Since the split, only the health factors sum to the score."""
        from benchmark_scoring import HEALTH_WEIGHTS

        trust = score_benchmark(find_benchmark("GPQA Diamond"))
        assert {f.name for f in trust.factors} == {
            "discrimination",
            "freshness",
            "reproducibility",
            "specificity",
        }
        # No penalties on this one, so health contributions should sum to
        # the health score. Specificity is reported but excluded.
        assert not trust.penalties
        health_factors = [f for f in trust.factors if f.name in HEALTH_WEIGHTS]
        assert sum(f.contribution for f in health_factors) == pytest.approx(
            trust.health, abs=0.2
        )

    def test_relevance_is_separate_and_never_multiplied_in(self):
        from dataclasses import replace

        gpqa = find_benchmark("GPQA Diamond")
        assert score_benchmark(gpqa).relevance == pytest.approx(
            gpqa.task_specificity * 100
        )
        # Changing relevance must not move health at all.
        shifted = replace(gpqa, specificity_dimensions=(2, 2, 2, 2, 2))
        assert score_benchmark(shifted).health == pytest.approx(
            score_benchmark(gpqa).health
        )
        assert score_benchmark(shifted).relevance == 100.0

    def test_health_weights_are_a_proportional_rescaling(self):
        """0.40/0.20/0.20 summed to 0.80; /0.80 gives 0.50/0.25/0.25."""
        from benchmark_scoring import HEALTH_WEIGHTS

        assert sum(HEALTH_WEIGHTS.values()) == pytest.approx(1.0)
        assert HEALTH_WEIGHTS["discrimination"] == pytest.approx(0.40 / 0.80)
        assert HEALTH_WEIGHTS["freshness"] == pytest.approx(0.20 / 0.80)
        assert HEALTH_WEIGHTS["reproducibility"] == pytest.approx(0.20 / 0.80)
        assert "specificity" not in HEALTH_WEIGHTS

    def test_measured_benchmarks_say_so(self):
        measured = score_benchmark(find_benchmark("MMLU"))
        curated = score_benchmark(find_benchmark("LiveCodeBench"))
        assert measured.measured_saturation is not None
        assert measured.models_measured > 0
        # LiveCodeBench still has no fetchable score export.
        assert curated.measured_saturation is None
        discrimination = {f.name: f for f in curated.factors}["discrimination"]
        assert discrimination.basis in ("curated", "unknown")

    def test_dominant_factor_is_the_weakest_one(self):
        trust = score_benchmark(find_benchmark("HellaSwag"))
        weakest = trust.dominant_factor
        assert all(weakest.value <= f.value for f in trust.factors)

    def test_freshness_halves_at_the_half_life(self):
        from datetime import date, timedelta

        recent = Benchmark(
            key="t1", name="T1", category="code generation",
            release_date=date.today().isoformat(), independent_evaluators=5,
            specificity_dimensions=(1, 1, 1, 1, 1),
        )
        older = Benchmark(
            key="t2", name="T2", category="code generation",
            release_date=(date.today() - timedelta(days=LEAKAGE_HALF_LIFE_DAYS)).isoformat(),
            independent_evaluators=5, specificity_dimensions=(1, 1, 1, 1, 1),
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
        assert load_benchmark_scores(find_benchmark("LiveCodeBench")) is None

    def test_trust_by_key_covers_the_catalog(self):
        by_key = trust_by_key()
        assert {b.key for b in load_benchmark_catalog()} == set(by_key)


class TestSpecificityRubric:
    """
    Specificity is the only factor with no measurement behind it, so the
    rubric decomposition is the whole of its accountability. v2 adopted
    by the owner 2026-09-21; see docs/SPECIFICITY_RUBRIC.md.
    """

    def test_every_benchmark_carries_its_dimension_scores(self):
        """A catalog entry with no rubric scoring has no specificity."""
        for b in load_benchmark_catalog():
            assert b.specificity_dimensions is not None, b.name
            assert len(b.specificity_dimensions) == 5, b.name
            assert all(d in (0, 1, 2) for d in b.specificity_dimensions), b.name

    def test_the_formula_is_the_sum_over_ten(self):
        from fetch_benchmarks import SPECIFICITY_MAX, specificity_from

        assert SPECIFICITY_MAX == 10
        assert specificity_from((0, 0, 0, 0, 0)) == 0.0
        assert specificity_from((2, 2, 2, 2, 2)) == 1.0
        assert specificity_from((1, 2, 2, 1, 0)) == pytest.approx(0.6)
        for b in load_benchmark_catalog():
            assert b.task_specificity == pytest.approx(
                sum(b.specificity_dimensions) / 10
            ), b.name

    def test_specificity_cannot_be_set_without_a_judgement(self):
        """
        No default. 0.5 would be a number nobody assigned, which is the
        exact failure the evidence standard exists to prevent.
        """
        from fetch_benchmarks import specificity_from

        with pytest.raises(ValueError):
            specificity_from(None)
        with pytest.raises(ValueError):
            specificity_from((1, 1, 1))
        with pytest.raises(ValueError):
            specificity_from((1, 1, 1, 1, 3))

    def test_multiple_choice_benchmarks_score_zero_on_who_does_this(self):
        """Rubric v2 edit 2: MC is D0 regardless of subject matter."""
        for name in ("MMLU", "MMLU-Pro", "GPQA Diamond", "HellaSwag",
                     "Winogrande", "TruthfulQA", "ARC (AI2 Reasoning Challenge)"):
            assert find_benchmark(name).specificity_dimensions[3] == 0, name

    def test_narrow_but_evaluation_only_tasks_do_not_score_two_on_scope(self):
        """Rubric v2 edit 3: narrowness alone does not earn a 2."""
        for name in ("Winogrande", "HellaSwag", "MuSR", "TruthfulQA"):
            assert find_benchmark(name).specificity_dimensions[2] <= 1, name

    def test_the_basis_names_the_rubric_and_admits_it_is_unchecked(self):
        for b in load_benchmark_catalog():
            assert "Rubric v2" in b.curation_notes, b.name
            assert "Not independently checked" in b.curation_notes, b.name

    def test_no_entry_still_claims_to_be_unreviewed_by_the_owner(self):
        """The four Claude-assigned values are now covered by the adoption."""
        for b in load_benchmark_catalog():
            assert "not yet reviewed by the owner" not in b.curation_notes, b.name
            assert "not been reviewed by the owner" not in b.curation_notes, b.name


class TestEvaluatorCountReach:
    """
    Where an unsourced curated count can and cannot change an answer.
    Winogrande and GSM8K both have two comparable score sources, so the
    measurement replaces the count today — but as-of scoring has no
    cross-source data, so the count is exactly what the backtest uses.
    """

    def _basis(self, name, as_of):
        trust = score_benchmark(find_benchmark(name), as_of=as_of)
        return {f.name: f for f in trust.factors}["reproducibility"]

    def test_the_count_is_ignored_today(self):
        for name in ("Winogrande", "GSM8K"):
            assert self._basis(name, None).basis == "measured", name

    def test_the_count_is_what_the_backtest_uses(self):
        from backtest import CUTOFF

        for name in ("Winogrande", "GSM8K"):
            assert self._basis(name, CUTOFF).basis == "curated", name

    def test_gsm8k_gets_full_credit_at_the_cutoff_and_0_13_today(self):
        """
        The widest gap in the catalog, pinned because it is a live weakness
        of the backtest rather than a curiosity: a benchmark whose scores
        demonstrably do not reproduce across harnesses (6.9 points of
        scatter, a 7.0-point systematic offset) is handed a perfect
        reproducibility score in 2024 on the strength of an evaluator count
        nobody has sourced.
        """
        from backtest import CUTOFF

        assert self._basis("GSM8K", CUTOFF).value == pytest.approx(1.0)
        assert self._basis("GSM8K", None).value < 0.2

    def test_both_counts_are_marked_as_partly_unsourced(self):
        for name in ("Winogrande", "GSM8K"):
            notes = find_benchmark(name).curation_notes
            assert "IS PARTLY UNSOURCED" in notes, name


class TestMusrBaseline:
    """
    Measured from the dataset by probes/musr_baseline.py, not read about.
    The murder-mystery split is binary, so 0.33 was never right.
    """

    def test_the_committed_baseline_matches_the_derivation(self):
        from fetch_benchmark_scores import RANDOM_BASELINES

        # (250 x 1/2 + 72.1333 + 250 x 1/3) / 756
        derived = (250 * 0.5 + (4 / 2 + 112 / 3 + 96 / 4 + 44 / 5) + 250 / 3) / 756
        assert derived == pytest.approx(0.371, abs=0.001)
        assert RANDOM_BASELINES["musr"] == pytest.approx(0.371)

    def test_the_stored_manifest_agrees_with_the_constant(self):
        """
        Scoring reads the manifest, the fetcher writes it from the
        constant. If they drift, saturation is computed against a baseline
        nothing in the code claims.
        """
        import json

        from fetch_benchmark_scores import RANDOM_BASELINES
        from fetch_benchmarks import SCORES_MANIFEST

        sets = json.loads(SCORES_MANIFEST.read_text())["sets"]
        for entry in sets.values():
            key = entry["benchmark_key"]
            if key in RANDOM_BASELINES and entry["normalization"] != "baseline":
                assert entry["random_baseline"] == pytest.approx(
                    RANDOM_BASELINES[key]
                ), key

    def test_dataset_size_is_the_counted_total(self):
        assert find_benchmark("MuSR").dataset_size == 756  # 250 + 256 + 250


class TestCuratedEvidence:
    """The curated research has to actually drive the numbers."""

    def test_contamination_penalty_scales_with_measured_rate(self):
        """MMLU (27.7% dirty) must be penalized harder than MMLU-Pro (16.2%)."""
        from benchmark_scoring import CONTAMINATION_PENALTY, FULL_CONTAMINATION_RATE

        mmlu = find_benchmark("MMLU")
        mmlu_pro = find_benchmark("MMLU-Pro")
        assert mmlu.contamination_rate > mmlu_pro.contamination_rate

        def multiplier(b):
            severity = min(b.contamination_rate / FULL_CONTAMINATION_RATE, 1.0)
            return 1.0 - (1.0 - CONTAMINATION_PENALTY) * severity

        assert multiplier(mmlu) < multiplier(mmlu_pro)

    def test_severe_inflation_outweighs_a_modest_overlap_rate(self):
        """HumanEval: 13% overlap, but scores fall 39.4% when decontaminated."""
        humaneval = find_benchmark("HumanEval")
        assert humaneval.contamination_rate < 0.2
        assert humaneval.contamination_effect > 0.35
        trust = score_benchmark(humaneval)
        # The effect, not the mild rate, should be driving the penalty.
        assert any("scores fall" in p for p in trust.penalties)
        assert trust.trust_score < 35

    def test_refreshed_benchmarks_do_not_age_like_static_ones(self):
        """LiveCodeBench's release windows are a defence against leakage."""
        from datetime import date, timedelta

        from fetch_benchmarks import Benchmark

        released = (date.today() - timedelta(days=900)).isoformat()
        static = Benchmark(
            key="s", name="S", category="code generation", release_date=released,
            specificity_dimensions=(1, 1, 1, 1, 1),
        )
        refreshed = Benchmark(
            key="r", name="R", category="code generation",
            release_date=released, holdout="refreshed",
            specificity_dimensions=(1, 1, 1, 1, 1),
        )
        static_freshness = {f.name: f for f in score_benchmark(static).factors}["freshness"]
        refreshed_freshness = {f.name: f for f in score_benchmark(refreshed).factors}["freshness"]
        assert refreshed_freshness.value > static_freshness.value

    def test_private_holdout_barely_ages(self):
        from fetch_benchmarks import Benchmark

        old_private = Benchmark(
            key="p", name="P", category="scientific reasoning",
            release_date="2020-01-01", holdout="private_holdout",
            specificity_dimensions=(1, 1, 1, 1, 1),
        )
        freshness = {f.name: f for f in score_benchmark(old_private).factors}["freshness"]
        assert freshness.value >= 0.9

    def test_gpqa_curated_flag_now_agrees_with_the_measurement(self):
        """Flag and measurement disagreeing was the signal; it's resolved."""
        gpqa = find_benchmark("GPQA Diamond")
        assert gpqa.saturation_flagged is True
        trust = score_benchmark(gpqa)
        # Measured over frontier models, where the question actually bites.
        assert trust.primary_source == "epoch_ai"
        assert trust.measured_saturation > 0.8

    def test_researched_entries_cite_their_sources(self):
        """A curated claim without a basis is a guess wearing a lab coat."""
        from fetch_benchmarks import load_benchmark_catalog

        for benchmark in load_benchmark_catalog():
            if benchmark.contamination_flagged or benchmark.saturation_flagged:
                notes = benchmark.curation_notes
                assert notes, f"{benchmark.name} is flagged with no curation notes"
                assert "RESEARCHED" in notes or "CURATE(you)" in notes, (
                    f"{benchmark.name} does not say whether its flags are researched"
                )

    def test_top_ranked_benchmarks_are_not_built_on_guesses(self):
        """
        The rankings must not be led by invented numbers.

        Every benchmark's trust score is driven by curated fields —
        evaluator count and task specificity alone are 40% of the weight.
        A benchmark that leads this table on values nobody researched is
        the failure mode this project exists to criticize, so the suite
        refuses it rather than trusting anyone to notice.
        """
        top = score_all_benchmarks()[:5]
        unresearched = [
            t.benchmark.name
            for t in top
            if "RESEARCHED" not in (t.benchmark.curation_notes or "")
        ]
        assert not unresearched, (
            "These benchmarks lead the rankings on uncurated fields: "
            f"{unresearched}. Research them or they should not be at the top."
        )

    def test_every_entry_states_the_basis_for_its_numbers(self):
        """Not just the leaders — no entry should be silently invented."""
        from fetch_benchmarks import load_benchmark_catalog

        missing = [
            b.name
            for b in load_benchmark_catalog()
            if "RESEARCHED" not in (b.curation_notes or "")
        ]
        assert not missing, f"Entries with no researched basis: {missing}"


class TestMeasurementPopulation:
    """Saturation depends on which models you measure over."""

    def test_frontier_source_is_preferred_over_a_bigger_sample(self):
        """4,575 weak models spread wide say nothing about the frontier."""
        from fetch_benchmarks import load_benchmark_scores as primary
        from fetch_benchmarks import load_score_sets

        gpqa = find_benchmark("GPQA Diamond")
        sets = {s.source: len(s.scores) for s in load_score_sets(gpqa)}
        assert sets["open_llm_leaderboard_v2"] > sets["epoch_ai"]
        assert primary(gpqa).source == "epoch_ai"

    def test_divergent_sources_are_reported_not_averaged(self):
        trust = score_benchmark(find_benchmark("GPQA Diamond"))
        assert len(trust.saturation_by_source) > 1
        discrimination = {f.name: f for f in trust.factors}["discrimination"]
        # The frontier reading leads; the community reading is named, not hidden.
        assert "frontier models" in discrimination.explanation
        assert "Note:" in discrimination.explanation

    def test_newly_measured_benchmarks_stop_guessing(self):
        """HumanEval, MMLU-Pro and TruthfulQA were curated-only before."""
        for name in ("HumanEval", "MMLU-Pro", "TruthfulQA"):
            trust = score_benchmark(find_benchmark(name))
            assert trust.measured_saturation is not None, f"{name} still unmeasured"
            assert trust.models_measured > 100
            basis = {f.name: f for f in trust.factors}["discrimination"].basis
            assert basis == "measured"

    def test_humaneval_measures_as_saturated(self):
        """The headline claim, now from a distribution rather than a citation."""
        trust = score_benchmark(find_benchmark("HumanEval"))
        assert trust.measured_saturation > 0.6


class TestPartialHoldout:
    """Hidden grading material is a real defence, short of a private set."""

    def _freshness(self, holdout, days_old=900):
        from datetime import date, timedelta

        from fetch_benchmarks import Benchmark

        released = (date.today() - timedelta(days=days_old)).isoformat()
        bench = Benchmark(
            key="t", name="T", category="code generation",
            release_date=released, holdout=holdout,
            specificity_dimensions=(1, 1, 1, 1, 1),
        )
        return {f.name: f for f in score_benchmark(bench).factors}["freshness"].value

    def test_partial_sits_between_public_and_refreshed(self):
        public = self._freshness("public_static")
        partial = self._freshness("partial_holdout")
        refreshed = self._freshness("refreshed")
        assert public < partial < refreshed

    def test_partial_is_well_below_private(self):
        assert self._freshness("partial_holdout") < self._freshness("private_holdout")

    def test_unknown_holdout_value_decays_fully(self):
        """An unrecognized value must not silently earn a discount."""
        assert self._freshness("nonsense") == self._freshness("public_static")

    def test_explanation_says_why(self):
        from datetime import date, timedelta

        from fetch_benchmarks import Benchmark

        bench = Benchmark(
            key="t", name="T", category="code generation",
            release_date=(date.today() - timedelta(days=900)).isoformat(),
            holdout="partial_holdout", specificity_dimensions=(1, 1, 1, 1, 1),
        )
        freshness = {f.name: f for f in score_benchmark(bench).factors}["freshness"]
        assert "grading material is withheld" in freshness.explanation

    def test_the_three_benchmarks_are_marked(self):
        for name in ("MirrorCode", "FrontierCode", "DeepSWE"):
            assert find_benchmark(name).holdout == "partial_holdout", name

    def test_no_other_entry_claims_partial_holdout_without_evidence(self):
        from fetch_benchmarks import load_benchmark_catalog

        for b in load_benchmark_catalog():
            if b.holdout == "partial_holdout":
                notes = b.curation_notes.lower()
                assert "held out" in notes or "held-out" in notes or "unpublished" in notes, (
                    f"{b.name} claims partial_holdout with no evidence in its notes"
                )


class TestItemQuality:
    """A wrong answer key is a defect, not a dimension."""

    def _rate(self, rate, basis="estimate"):
        from benchmark_scoring import score_benchmark
        from fetch_benchmarks import Benchmark

        return score_benchmark(
            Benchmark(
                key="t", name="T", category="code generation",
                release_date="2026-01-01", independent_evaluators=3,
                specificity_dimensions=(2, 2, 2, 1, 1),  # 8/10 = 0.8
                item_error_rate=rate,
                item_error_rate_basis=basis,
            )
        )

    def test_errors_lower_the_score_in_proportion(self):
        clean = self._rate(None)
        mild = self._rate(0.05)
        severe = self._rate(0.30)
        assert clean.trust_score > mild.trust_score > severe.trust_score

    def test_unaudited_is_not_treated_as_clean_or_as_zero(self):
        """None means nobody looked — no penalty, and no credit either."""
        unaudited = self._rate(None)
        assert not any("mislabelled" in p for p in unaudited.penalties)
        # An explicit 0.0 is a *clean audit* and should also not be penalized.
        audited_clean = self._rate(0.0)
        assert audited_clean.trust_score == unaudited.trust_score

    def test_penalty_saturates_rather_than_going_negative(self):
        from benchmark_scoring import ITEM_ERROR_PENALTY

        catastrophic = self._rate(0.95)
        floor = self._rate(0.20)
        assert catastrophic.trust_score == pytest.approx(floor.trust_score, abs=0.05)
        assert catastrophic.trust_score > 0
        assert ITEM_ERROR_PENALTY > 0

    def test_penalty_is_named_in_the_breakdown(self):
        trust = self._rate(0.36)
        assert any("36% of items" in p for p in trust.penalties)

    def test_real_entries_carry_their_audited_rates(self):
        assert find_benchmark("MMLU").item_error_rate == pytest.approx(0.0649)
        assert find_benchmark("HellaSwag").item_error_rate == pytest.approx(0.36)
        # A floor derived from OpenAI's partial audit, not a point estimate:
        # 59.4% of an audited 27.6% is ~16.4% of the whole benchmark.
        assert find_benchmark("SWE-Bench Verified").item_error_rate == pytest.approx(0.164)

    def test_an_estimate_reads_as_a_point_value(self):
        trust = self._rate(0.164, basis="estimate")
        assert any(p == "16% of items are mislabelled or misgraded" for p in trust.penalties), (
            trust.penalties
        )

    def test_a_lower_bound_reads_as_at_least(self):
        trust = self._rate(0.164, basis="lower_bound")
        assert any(
            p == "at least 16% of items are mislabelled or misgraded"
            for p in trust.penalties
        ), trust.penalties

    def test_the_basis_changes_wording_but_never_the_score(self):
        """
        A floor of 16% and an estimate of 16% are the same amount of
        demonstrated breakage. Scoring the bound harder would mean
        inventing a severity the audit did not establish.
        """
        for rate in (0.03, 0.164, 0.45):
            assert self._rate(rate, "lower_bound").trust_score == pytest.approx(
                self._rate(rate, "estimate").trust_score
            )

    def test_the_default_basis_is_estimate(self):
        from fetch_benchmarks import Benchmark, load_benchmark_catalog

        assert Benchmark(
            key="t", name="T", category="code generation",
            specificity_dimensions=(1, 1, 1, 1, 1),
        ).item_error_rate_basis == (
            "estimate"
        )
        bounded = [
            b.name for b in load_benchmark_catalog()
            if b.item_error_rate_basis == "lower_bound"
        ]
        assert bounded == ["SWE-Bench Verified"], bounded

    def test_every_basis_is_one_of_the_two_allowed_values(self):
        from fetch_benchmarks import load_benchmark_catalog

        for b in load_benchmark_catalog():
            assert b.item_error_rate_basis in ("estimate", "lower_bound"), b.name

    def test_swe_bench_states_its_floor_in_the_breakdown(self):
        trust = score_benchmark(find_benchmark("SWE-Bench Verified"))
        assert any(p.startswith("at least 16%") for p in trust.penalties), trust.penalties

    def test_unaudited_benchmarks_stay_none(self):
        """Most of the catalog has never been audited; that must show as None."""
        from fetch_benchmarks import load_benchmark_catalog

        unaudited = [b for b in load_benchmark_catalog() if b.item_error_rate is None]
        assert len(unaudited) >= 15, "suspiciously many benchmarks claim an audited rate"

    def test_every_audited_rate_cites_a_source(self):
        from fetch_benchmarks import load_benchmark_catalog

        for b in load_benchmark_catalog():
            if b.item_error_rate is not None:
                notes = b.curation_notes.lower()
                assert "item" in notes or "label error" in notes, (
                    f"{b.name} has an item_error_rate with no explanation"
                )


class TestNewlyAddedBenchmarks:
    """The four added to complete HF's June 2024 retirement decision."""

    def test_all_six_retired_benchmarks_are_catalogued(self):
        for name in ("ARC (AI2 Reasoning Challenge)", "HellaSwag", "MMLU",
                     "TruthfulQA", "Winogrande", "GSM8K"):
            benchmark = find_benchmark(name)
            assert benchmark is not None, f"{name} missing"
            assert benchmark.saturation_flagged, f"{name} not flagged"
            assert benchmark.evidence_dates.get("saturation_flagged") == "2024-06-26"

    def test_all_six_replacements_are_catalogued(self):
        for name in ("MMLU-Pro", "GPQA Diamond", "BIG-Bench Hard",
                     "MATH Level 5", "MuSR", "IFEval"):
            assert find_benchmark(name) is not None, f"{name} missing"

    def test_the_new_entries_have_measured_saturation(self):
        for name in ("Winogrande", "GSM8K", "MuSR", "IFEval"):
            trust = score_benchmark(find_benchmark(name))
            assert trust.measured_saturation is not None, name
            assert trust.models_measured > 100, name

    def test_musr_reads_the_raw_column_not_the_rescaled_one(self):
        """
        The GPQA trap, and MuSR is its worst case: raw runs 0.29-0.60 while
        the rescaled column runs 0-38.7. Reading the wrong one would make
        every model look near-random.
        """
        from fetch_benchmarks import load_score_sets

        scores = load_score_sets(find_benchmark("MuSR"))[0]
        assert scores.normalization == "none"
        assert 0.2 < min(scores.scores) and max(scores.scores) < 0.7

    def test_the_unverified_figure_was_resolved_by_probing(self):
        """
        MuSR's widely-quoted 756 was left None while it was only hearsay.
        It has since been counted from the released dataset — 250 + 256 +
        250 — so it is now recorded as a measurement rather than dropped.
        The rule was never "leave it out", it was "don't record hearsay".
        """
        musr = find_benchmark("MuSR")
        assert musr.dataset_size == 756
        assert "MEASURED 2026-09-21 by probing" in musr.curation_notes

    def test_gsm8k_records_a_mean_not_the_published_maximum(self):
        """
        Resolved 2026-09-21. The paper's headline "up to 8%" is a MAXIMUM
        across models; every contamination_effect here is a mean across a
        model set, so storing 0.08 would have compared different
        quantities. probes/gsm1k_effect.py extracts the per-model table
        from the paper and takes the mean relative drop: 0.051.
        """
        gsm8k = find_benchmark("GSM8K")
        assert gsm8k.contamination_flagged
        assert gsm8k.contamination_effect == pytest.approx(0.051)
        # Not the maximum, and not the absolute-points figure.
        assert gsm8k.contamination_effect < 0.08
        assert "MEAN of those" in gsm8k.curation_notes
        # 63 models, reproducible from the paper.
        assert "probes/gsm1k_effect.py" in gsm8k.curation_notes

    def test_the_gsm1k_evidence_predates_the_backtest_cutoff(self):
        """
        Unlike almost every other piece of evidence in this catalog, this
        one IS visible to the backtest — the paper is dated 2024-05-01 and
        the cutoff is 2024-06-01. Pinned because that is unusual and makes
        this value one of the few that can move the backtest.
        """
        gsm8k = find_benchmark("GSM8K")
        assert gsm8k.evidence_dates["contamination_effect"] == "2024-05-01"
        assert gsm8k.known_at("contamination_effect", "2024-06-01")

        then = score_benchmark(gsm8k, as_of="2024-06-01")
        assert any("scores fall" in p for p in then.penalties), then.penalties

    def test_the_two_effect_figures_are_not_the_same_measurement(self):
        """
        Both HumanEval (0.394) and GSM8K (0.051) sit in contamination_effect
        and the penalty treats them identically, but GSM1k controlled for
        difficulty and EvoEval did not. The catalog has to say so.
        """
        humaneval = find_benchmark("HumanEval")
        assert humaneval.contamination_effect == pytest.approx(0.394)
        assert "NOT A CLEAN CONTAMINATION EFFECT" in humaneval.curation_notes
        assert "EvoEval" in humaneval.curation_notes
        # And the miscitation is recorded rather than silently fixed.
        assert "CITATION CORRECTED" in humaneval.curation_notes

    def test_instruction_following_category_is_matchable(self):
        from task_matcher import match_task

        assert match_task("does it follow output formatting constraints").category == (
            "instruction following"
        )


class TestPopulationIsRecorded:
    """
    Saturation is a property of a population snapshot, not of a
    benchmark. Every reading has to say which population, or a reader
    compares two numbers that answer different questions.
    """

    def test_every_score_set_names_its_population(self):
        from fetch_benchmarks import load_score_sets

        for b in load_benchmark_catalog():
            for scores in load_score_sets(b):
                assert scores.population, b.name
                # Derived from the manifest's source, not invented.
                assert scores.population != scores.source or scores.source not in (
                    "epoch_ai", "open_llm_leaderboard_v1",
                    "open_llm_leaderboard_v2", "evalplus",
                )

    def test_trust_names_the_population_it_was_measured_on(self):
        for b in load_benchmark_catalog():
            trust = score_benchmark(b)
            if trust.measured_saturation is None:
                assert trust.population is None, b.name
            else:
                assert trust.population, b.name

    def test_the_same_benchmark_reads_differently_by_population(self):
        """The reason the field exists, pinned as a fact."""
        gpqa = score_benchmark(find_benchmark("GPQA Diamond"))
        readings = gpqa.saturation_by_source
        assert len(readings) == 2
        frontier = readings["epoch_ai"][0]
        community = readings["open_llm_leaderboard_v2"][0]
        assert frontier - community > 0.25, (frontier, community)


class TestUiWarnsAboutMixedPopulations:
    def test_a_mixed_category_carries_the_warning(self):
        import app

        header, _ = app.rank_benchmarks("general knowledge questions")
        assert "not a like-for-like ranking" in header
        assert "2 populations" in header

    def test_a_single_population_category_does_not(self):
        import app

        header, _ = app.rank_benchmarks("scientific reasoning questions")
        assert "not a like-for-like ranking" not in header

    def test_every_row_names_its_population(self):
        import app

        _, frame = app.rank_benchmarks("general knowledge questions")
        assert "measured over" in frame.columns
        assert all(str(v).strip() for v in frame["measured over"])


class TestContaminationEffectBasis:
    """
    0.394 (EvoEval, difficulty uncontrolled) and 0.051 (GSM1k,
    difficulty-matched) sit in the same field. The penalty cannot tell
    them apart, so the wording has to.
    """

    def test_the_default_is_the_pessimistic_reading(self):
        """Assuming a study controlled for difficulty is the optimistic error."""
        from fetch_benchmarks import Benchmark

        assert Benchmark(
            key="t", name="T", category="code generation",
            specificity_dimensions=(1, 1, 1, 1, 1),
        ).contamination_effect_basis == "uncontrolled"

    def test_every_basis_is_one_of_the_two_allowed_values(self):
        for b in load_benchmark_catalog():
            assert b.contamination_effect_basis in (
                "difficulty_controlled", "uncontrolled"
            ), b.name

    def test_only_gsm8k_claims_difficulty_control(self):
        controlled = [
            b.name for b in load_benchmark_catalog()
            if b.contamination_effect_basis == "difficulty_controlled"
        ]
        assert controlled == ["GSM8K"], controlled

    def test_the_two_render_differently(self):
        gsm8k = score_benchmark(find_benchmark("GSM8K"))
        humaneval = score_benchmark(find_benchmark("HumanEval"))
        assert any("difficulty-matched" in p for p in gsm8k.penalties), gsm8k.penalties
        assert any("was not controlled" in p for p in humaneval.penalties), (
            humaneval.penalties
        )

    def test_the_basis_changes_wording_but_never_the_score(self):
        from dataclasses import replace

        humaneval = find_benchmark("HumanEval")
        flipped = replace(humaneval, contamination_effect_basis="difficulty_controlled")
        assert score_benchmark(flipped).trust_score == pytest.approx(
            score_benchmark(humaneval).trust_score
        )

    def test_benchmarks_with_no_effect_are_unaffected(self):
        """MMLU and MMLU-Pro have a rate but no effect; the basis is moot."""
        for name in ("MMLU", "MMLU-Pro"):
            b = find_benchmark(name)
            assert b.contamination_effect is None
            assert not any(
                "difficulty" in p for p in score_benchmark(b).penalties
            ), name
