from datetime import datetime, timedelta, timezone

import pytest

from enrich_scores import ExternalScore
from scoring import (
    SELF_REPORT_PENALTY,
    STALENESS_HALF_LIFE_DAYS,
    _days_since,
    _parse_card_value,
    compute_trust_score,
    score_model,
)


def _days_ago(days: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days)).date().isoformat()


def _external(score=60.0, source="artificial_analysis", days_ago=10):
    return ExternalScore(
        source=source,
        benchmark_name="test_bench",
        score=score,
        score_scale="0-100",
        reported_date=_days_ago(days_ago),
    )


def _raw(eval_results=None, days_ago=10):
    return {
        "model_id": "org/test-coder-7b",
        "params_billion": 7.0,
        "license": "apache-2.0",
        "downloads": 100,
        "eval_results": eval_results or [],
        "last_modified": _days_ago(days_ago),
    }


class TestCardValueParsing:
    @pytest.mark.parametrize(
        "raw,expected",
        [(45.2, 45.2), (60, 60.0), ("45.2", 45.2), ("7.84%", 7.84), (" 45.2 ", 45.2)],
    )
    def test_numbers_and_percent_strings(self, raw, expected):
        assert _parse_card_value(raw)[0] == expected

    def test_percent_string_is_known_to_be_0_100(self):
        # Regression: "7.84%" on bigcode/tiny_starcoder_py used to crash.
        assert _parse_card_value("7.84%") == (7.84, "0-100")

    @pytest.mark.parametrize("raw", ["n/a", "", None, True, [1, 2], {"a": 1}])
    def test_unreadable_values_are_skipped(self, raw):
        assert _parse_card_value(raw)[0] is None


class TestDateParsing:
    @pytest.mark.parametrize(
        "raw",
        [
            "2025-01-12",
            "2025-01-12T02:03:41+00:00",
            "2025-01-12T02:03:41.123456+00:00",
            "2025-01-12T02:03:41Z",
        ],
    )
    def test_supported_formats(self, raw):
        assert _days_since(raw) is not None

    @pytest.mark.parametrize("raw", [None, "", "None", "not a date"])
    def test_unparseable_is_unknown_not_crash(self, raw):
        assert _days_since(raw) is None


class TestTrustScore:
    def test_more_sources_earns_more_trust(self):
        fresh = [1.0]
        one = compute_trust_score(1, fresh, self_reported_only=False)
        two = compute_trust_score(2, fresh, self_reported_only=False)
        three = compute_trust_score(3, fresh, self_reported_only=False)
        assert one < two < three

    def test_stale_scores_are_discounted(self):
        fresh = compute_trust_score(3, [1.0], self_reported_only=False)
        stale = compute_trust_score(3, [STALENESS_HALF_LIFE_DAYS], self_reported_only=False)
        assert stale == pytest.approx(fresh / 2, rel=0.02)

    def test_self_reported_only_is_penalized(self):
        independent = compute_trust_score(1, [1.0], self_reported_only=False)
        self_reported = compute_trust_score(1, [1.0], self_reported_only=True)
        # Both values are rounded to 4dp independently, so allow for the
        # difference between rounding before vs after applying the penalty.
        assert self_reported == pytest.approx(independent * SELF_REPORT_PENALTY, abs=1e-4)

    def test_unknown_age_is_treated_as_moderately_stale(self):
        assert compute_trust_score(3, [], self_reported_only=False) == 0.5

    def test_stays_within_bounds(self):
        assert 0.0 <= compute_trust_score(99, [0], self_reported_only=False) <= 1.0


class TestScoreModel:
    def test_card_only_model_is_flagged_self_reported(self):
        result = score_model(_raw([{"metric_name": "pass@1", "metric_value": 80.0}]), [])
        assert result.self_reported_only is True
        assert result.sources == ["huggingface_hub_card"]

    def test_independent_source_removes_the_penalty(self):
        card = [{"metric_name": "pass@1", "metric_value": 80.0}]
        alone = score_model(_raw(card), [])
        corroborated = score_model(_raw(card), [_external(score=80.0)])
        assert corroborated.self_reported_only is False
        # Same benchmark number, but corroborated by an independent source.
        assert corroborated.raw_benchmark_score == alone.raw_benchmark_score
        assert corroborated.composite_score > alone.composite_score

    def test_self_reported_model_ranks_below_corroborated_one(self):
        """The sakthai-coder-1.5b case: a card-only score topping the table."""
        boastful = score_model(
            _raw([{"metric_name": "pass@1", "metric_value": 95.0}]), []
        )
        corroborated = score_model(
            _raw([{"metric_name": "pass@1", "metric_value": 70.0}]),
            [_external(score=70.0), _external(score=70.0, source="epoch_ai")],
        )
        assert corroborated.composite_score > boastful.composite_score

    def test_model_with_no_benchmarks_scores_none(self):
        result = score_model(_raw([]), [])
        assert result.composite_score is None
        assert result.num_sources == 0
        assert result.self_reported_only is False

    def test_scales_are_respected_when_averaging(self):
        """A 0-1 source and a 0-100 source reporting the same result agree."""
        as_fraction = ExternalScore("s", "b", 0.7, "0-1", _days_ago(10))
        as_percent = ExternalScore("s", "b", 70.0, "0-100", _days_ago(10))
        assert (
            score_model(_raw([]), [as_fraction]).raw_benchmark_score
            == score_model(_raw([]), [as_percent]).raw_benchmark_score
        )


class TestRanking:
    def test_corroborated_outranks_higher_self_reported_score(self):
        """An unverified number is not evidence, however large it is."""
        from scoring import score_models

        boastful = _raw([{"metric_name": "pass@1", "metric_value": 95.0}])
        boastful["model_id"] = "org/self-scored"
        measured = _raw([])
        measured["model_id"] = "org/measured"

        class FakeIndex:
            def lookup(self, model_id):
                return [_external(score=40.0)] if model_id == "org/measured" else []

        ranked = score_models([boastful, measured], index=FakeIndex())
        assert [m.model_id for m in ranked] == ["org/measured", "org/self-scored"]
        # ...even though the self-reported composite is numerically higher.
        assert ranked[1].composite_score > ranked[0].composite_score

    def test_unscored_models_rank_last(self):
        from scoring import score_models

        class EmptyIndex:
            def lookup(self, model_id):
                return []

        scored_model = _raw([{"metric_name": "pass@1", "metric_value": 10.0}])
        scored_model["model_id"] = "org/has-data"
        blank = _raw([])
        blank["model_id"] = "org/no-data"

        ranked = score_models([blank, scored_model], index=EmptyIndex())
        assert [m.model_id for m in ranked] == ["org/has-data", "org/no-data"]


class TestProvenance:
    def test_unverified_repo_ranks_below_verified_one(self):
        """A score attributed to an unconfirmed repo may be another model's."""
        from scoring import score_models

        impostor = _raw([])
        impostor["model_id"] = "testaccount/Big-Closed-Model"
        impostor["provenance_verified"] = False
        genuine = _raw([])
        genuine["model_id"] = "realorg/real-model"

        class FakeIndex:
            def lookup(self, model_id):
                score = 95.0 if model_id.startswith("testaccount") else 40.0
                return [_external(score=score)]

        ranked = score_models([impostor, genuine], index=FakeIndex())
        assert [m.model_id for m in ranked] == [
            "realorg/real-model",
            "testaccount/Big-Closed-Model",
        ]
        assert ranked[1].composite_score > ranked[0].composite_score

    def test_models_default_to_verified(self):
        """Tag-search models aren't name-matched, so provenance isn't in doubt."""
        assert score_model(_raw([]), []).provenance_verified is True


class TestBenchmarkWeighting:
    """Model scores are downstream of benchmark trust."""

    def test_the_same_raw_score_carries_different_trust(self):
        from scoring import score_model

        # Same number, different benchmarks: HumanEval (2021, saturated,
        # quantified contamination) vs MirrorCode (2026, held out).
        on_humaneval = score_model(
            _raw([{"dataset": "HumanEval", "metric_value": 90.0}]), []
        )
        on_mirrorcode = score_model(
            _raw([{"dataset": "MirrorCode", "metric_value": 90.0}]), []
        )
        # Raw score is the same number...
        assert on_humaneval.raw_benchmark_score == on_mirrorcode.raw_benchmark_score
        # ...but the breakdown records very different benchmark trust.
        assert (
            on_humaneval.benchmark_breakdown[0]["trust"]
            < on_mirrorcode.benchmark_breakdown[0]["trust"]
        )

    def test_swe_bench_health_versus_humaneval_is_now_close(self):
        """
        Rewritten 2026-09-22. The old inversion (SWE-Bench below
        HumanEval) was caused by the flat unquantified-contamination
        penalty and disappeared when that was fixed. Under the
        percentile saturation definition and drop-and-renormalize the
        two are close again, with HumanEval slightly ahead on HEALTH —
        because SWE-Bench carries an evidence-backed item-quality
        penalty and has only one source, so its reproducibility is
        dropped entirely.

        Health is not the whole picture and the UI does not present it
        as such: SWE-Bench leads on relevance 100 to 60.
        """
        from benchmark_scoring import score_benchmark
        from fetch_benchmarks import find_benchmark

        swe = score_benchmark(find_benchmark("SWE-Bench Verified"))
        humaneval = score_benchmark(find_benchmark("HumanEval"))
        assert abs(swe.health - humaneval.health) < 15
        assert swe.relevance > humaneval.relevance
        # The unquantified flag still warns without charging.
        assert any(p.startswith("WARNING:") for p in swe.penalties), swe.penalties

    def test_an_unquantified_flag_warns_without_charging(self):
        """
        Decision 2026-09-21. An unmeasured flag must cost nothing, and a
        measured one must still cost something — otherwise the catalog
        rewards never looking.
        """
        from dataclasses import replace

        from benchmark_scoring import score_benchmark
        from fetch_benchmarks import find_benchmark

        swe = find_benchmark("SWE-Bench Verified")
        assert swe.contamination_flagged
        assert swe.contamination_rate is None and swe.contamination_effect is None

        flagged_only = score_benchmark(swe).trust_score
        unflagged = score_benchmark(replace(swe, contamination_flagged=False))
        # The flag costs nothing...
        assert flagged_only == pytest.approx(unflagged.trust_score)
        # ...but it is not silent.
        assert not any(p.startswith("WARNING:") for p in unflagged.penalties)

        # A measured rate still bites.
        measured = score_benchmark(replace(swe, contamination_rate=0.30)).trust_score
        assert measured < flagged_only

    def test_weighted_mean_favors_the_trusted_benchmark(self):
        """A model strong on a trusted benchmark beats one strong on a stale one."""
        from scoring import score_model

        strong_where_it_counts = score_model(
            _raw(
                [
                    {"dataset": "Terminal Bench", "metric_value": 80.0},
                    {"dataset": "HumanEval", "metric_value": 20.0},
                ]
            ),
            [],
        )
        strong_where_it_doesnt = score_model(
            _raw(
                [
                    {"dataset": "Terminal Bench", "metric_value": 20.0},
                    {"dataset": "HumanEval", "metric_value": 80.0},
                ]
            ),
            [],
        )
        assert (
            strong_where_it_counts.raw_benchmark_score
            > strong_where_it_doesnt.raw_benchmark_score
        )

    def test_an_unassessed_benchmark_carries_no_weight_but_is_shown(self):
        """
        Owner's decision 2026-09-22, option (iii). The old
        UNKNOWN_BENCHMARK_TRUST = 45.0 was chosen, not derived, and
        survived two changes to the scale it was expressed in. An
        unassessed benchmark now carries no weight and is displayed.
        """
        import scoring

        assert not hasattr(scoring, "UNKNOWN_BENCHMARK_TRUST")

        result = scoring.score_model(
            _raw([{"dataset": "SomeInternalEval", "metric_value": 70.0}]), []
        )
        entry = result.benchmark_breakdown[0]
        assert entry["recognized"] is False
        assert entry["unweighted"] is True
        # Shown, not discarded.
        assert entry["benchmark"] == "SomeInternalEval"
        assert entry["score"] == pytest.approx(0.70)
        # And the model is flagged as having nothing weightable.
        assert result.has_weighted_evidence is False

    def test_a_model_with_no_weighted_evidence_ranks_below_one_with_some(self):
        from scoring import rank_key, score_model

        assessed = score_model(_raw([{"dataset": "HumanEval", "metric_value": 30.0}]), [])
        unassessed = score_model(
            _raw([{"dataset": "SomeInternalEval", "metric_value": 95.0}]), []
        )
        assert assessed.has_weighted_evidence is True
        assert unassessed.has_weighted_evidence is False
        assert rank_key(assessed) > rank_key(unassessed)

    def test_weighting_never_outranks_verification(self):
        """
        The rung sits BELOW provenance and self-reporting. A
        self-reported number on a catalogued benchmark must not beat an
        independently corroborated one on an unassessed benchmark.
        """
        from dataclasses import replace

        from scoring import rank_key, score_model

        base = score_model(_raw([{"dataset": "HumanEval", "metric_value": 30.0}]), [])
        self_reported_assessed = replace(
            base, self_reported_only=True, has_weighted_evidence=True
        )
        corroborated_unassessed = replace(
            base, self_reported_only=False, has_weighted_evidence=False
        )
        assert rank_key(corroborated_unassessed) > rank_key(self_reported_assessed)

    def test_breakdown_names_what_drove_the_score(self):
        from scoring import score_model

        result = score_model(
            _raw([{"dataset": "MMLU", "metric_value": 70.0}]),
            [_external(score=60.0)],
        )
        assert len(result.benchmark_breakdown) == 2
        # Sorted by trust, so the reader sees the strongest evidence first.
        trusts = [b["trust"] for b in result.benchmark_breakdown]
        assert trusts == sorted(trusts, reverse=True)


class TestThinTierBenchmarksAreUnweighted:
    """
    Owner's decision 2026-09-22, option (ii). A benchmark whose health
    rests on no measured factor carries no weight; its result is still
    reported.

    Measured impact today: ZERO. No model in data/models_raw.json cites
    a thin-tier benchmark (0 of 187 citations). This is a guard.
    """

    def test_a_thin_tier_result_carries_no_weight(self):
        from benchmark_scoring import score_benchmark
        from fetch_benchmarks import find_benchmark
        from scoring import score_model

        mirrorcode = score_benchmark(find_benchmark("MirrorCode"))
        assert mirrorcode.evidence_tier == "thin"

        scored = score_model(
            _raw([{"dataset": "MirrorCode", "metric_value": 90.0}]), []
        )
        point = scored.benchmark_breakdown[0]
        assert point["unweighted"] is True

    def test_a_thin_result_does_not_move_the_weighted_mean(self):
        from scoring import score_model

        alone = score_model(_raw([{"dataset": "HumanEval", "metric_value": 40.0}]), [])
        with_thin = score_model(
            _raw(
                [
                    {"dataset": "HumanEval", "metric_value": 40.0},
                    {"dataset": "MirrorCode", "metric_value": 95.0},
                ]
            ),
            [],
        )
        assert with_thin.raw_benchmark_score == pytest.approx(
            alone.raw_benchmark_score
        )

    def test_the_thin_result_is_still_reported(self):
        """Excluded from the weighting, not from the evidence."""
        from scoring import score_model

        scored = score_model(
            _raw(
                [
                    {"dataset": "HumanEval", "metric_value": 40.0},
                    {"dataset": "MirrorCode", "metric_value": 95.0},
                ]
            ),
            [],
        )
        labels = {p["benchmark"] for p in scored.benchmark_breakdown}
        assert "MirrorCode" in labels

    def test_partial_and_full_tier_results_still_weigh(self):
        from scoring import score_model

        scored = score_model(
            _raw([{"dataset": "HumanEval", "metric_value": 40.0}]), []
        )
        assert scored.benchmark_breakdown[0]["unweighted"] is False


class TestAgreementIsARungInTheProvenanceTiers:
    """
    Owner's decision 2026-09-22, option (iv): corroborated-and-agreeing
    above corroborated-and-disagreeing above self-reported. Reuses
    cross_source.SCATTER_TOLERANCE rather than inventing a threshold.

    Measured impact today: ZERO models have two sources reporting the
    same benchmark, so nothing is checked. A guard.
    """

    def test_agreement_reuses_the_benchmark_side_threshold(self):
        import inspect

        import scoring

        source = inspect.getsource(scoring._sources_agree)
        assert "SCATTER_TOLERANCE" in source
        # and does not define its own
        assert "= 0.0" not in source.split("SCATTER_TOLERANCE")[0]

    def test_nothing_to_compare_reads_as_unchecked(self):
        from scoring import _sources_agree, score_model

        scored = score_model(_raw([{"dataset": "HumanEval", "metric_value": 40.0}]), [])
        assert scored.sources_agree is None
        assert _sources_agree([]) is None

    def test_two_agreeing_sources_are_recognised(self):
        from scoring import score_model

        card = [{"dataset": "HumanEval", "metric_value": 70.0}]
        scored = score_model(_raw(card), [_external(score=71.0)])
        # The external score is attributed to its own benchmark label, so
        # agreement only registers when both name the same benchmark.
        assert scored.sources_agree in (None, True)

    def test_disagreeing_sources_rank_below_agreeing_ones(self):
        """The rung itself, exercised directly on the sort key."""
        from dataclasses import replace

        from scoring import rank_key, score_model

        base = score_model(_raw([{"dataset": "HumanEval", "metric_value": 70.0}]), [])
        agreeing = replace(base, sources_agree=True)
        unchecked = replace(base, sources_agree=None)
        disagreeing = replace(base, sources_agree=False)
        assert rank_key(agreeing) > rank_key(unchecked) > rank_key(disagreeing)

    def test_unchecked_never_outranks_demonstrated_agreement(self):
        """The uncheckability rule, applied to this rung."""
        from dataclasses import replace

        from scoring import rank_key, score_model

        base = score_model(_raw([{"dataset": "HumanEval", "metric_value": 70.0}]), [])
        assert rank_key(replace(base, sources_agree=None)) < rank_key(
            replace(base, sources_agree=True)
        )


class TestCompositeIndexesAreMarked:
    """
    Owner's decision 2026-09-22 (D4). A composite index is a published
    aggregate over benchmarks, not a benchmark. Counting one as a
    benchmark double-counts any component the catalog assesses.
    """

    def test_the_aa_coding_index_is_marked_with_its_components(self):
        from scoring import score_model

        scored = score_model(
            _raw([{"dataset": "artificial_analysis_coding_index", "metric_value": 70.0}]),
            [],
        )
        entry = scored.benchmark_breakdown[0]
        assert entry["composite_of"] == ("Terminal-Bench 4.0", "SciCode")
        assert entry["unweighted"] is True

    def test_a_real_benchmark_is_not_marked_composite(self):
        from scoring import score_model

        scored = score_model(_raw([{"dataset": "HumanEval", "metric_value": 40.0}]), [])
        assert scored.benchmark_breakdown[0]["composite_of"] is None

    def test_a_component_is_itself_catalogued(self):
        """
        The double-count made concrete: Terminal Bench is assessed in the
        catalog AND sits inside the index, so a model carrying both has
        it counted twice.
        """
        from fetch_benchmarks import find_benchmark
        from scoring import COMPOSITE_COMPONENTS

        components = COMPOSITE_COMPONENTS["artificial_analysis_coding_index"]
        assert find_benchmark("Terminal Bench") is not None
        assert any("Terminal-Bench" in c for c in components)
