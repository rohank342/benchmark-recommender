"""The backtest is only meaningful if it cannot see the future."""
import pytest

from backtest import CUTOFF, REPLACEMENTS, RETIRED, confusion, run_retirement_test, separation
from benchmark_scoring import score_benchmark
from fetch_benchmarks import find_benchmark, load_score_sets


class TestNoLeakage:
    def test_retirement_derived_flags_are_invisible_at_the_cutoff(self):
        """
        The four retired benchmarks carry saturation_flagged *because* they
        were retired. If as-of scoring could see that, the test would be
        marking its own homework.
        """
        for name in RETIRED:
            benchmark = find_benchmark(name)
            assert benchmark.saturation_flagged, f"{name} should be flagged today"
            assert not benchmark.known_at("saturation_flagged", CUTOFF), (
                f"{name}'s saturation flag leaks into the backtest"
            )

    def test_post_cutoff_models_are_excluded(self):
        for name in RETIRED + REPLACEMENTS:
            for scores in load_score_sets(find_benchmark(name)):
                filtered = scores.before(CUTOFF)
                assert all(d < CUTOFF for d in filtered.model_dates)

    def test_undated_models_are_dropped_not_assumed_old(self):
        """Including an undated model could import a post-cutoff result."""
        scores = load_score_sets(find_benchmark("HumanEval"))[0]
        assert scores.dated == 0  # EvalPlus publishes no dates
        assert len(scores.before(CUTOFF).scores) == 0

    def test_undated_evidence_is_unavailable_when_time_travelling(self):
        triviaqa = find_benchmark("TriviaQA")
        assert triviaqa.contamination_flagged
        assert not triviaqa.known_at("contamination_flagged", CUTOFF)
        # ...but still counts when scoring today.
        assert triviaqa.known_at("contamination_flagged", None)

    def test_cross_source_agreement_is_not_used_when_time_travelling(self):
        """Today's score sets can't prove what two evaluators said in 2024."""
        trust = score_benchmark(find_benchmark("MMLU"), as_of=CUTOFF)
        assert trust.agreement is None
        factor = {f.name: f for f in trust.factors}["reproducibility"]
        assert factor.basis == "curated"

    def test_evidence_published_after_the_cutoff_is_excluded(self):
        """MMLU's contamination rate is a 2025 finding."""
        mmlu = find_benchmark("MMLU")
        assert mmlu.contamination_rate is not None
        assert not mmlu.known_at("contamination_rate", CUTOFF)
        then = score_benchmark(mmlu, as_of=CUTOFF)
        assert not any("pretraining data" in p for p in then.penalties)


class TestResult:
    def test_the_result_is_ten_of_twelve(self):
        """
        Re-pinned 2026-09-22 after unmeasurable factors stopped
        contributing. 8/12 -> 10/12, gap -20.6 -> -10.3.

        THIS IS NOT VINDICATION. The change was made because the curated
        fallback paid more than the measurement it replaced (curated mean
        0.580 vs measured 0.485), which is an evidence argument that
        stands whatever the test does. It happened to help; the split
        before it happened to hurt. Neither was chosen for its effect
        here, and nothing may be.
        """
        outcomes = run_retirement_test()
        matrix = confusion(outcomes)
        correct = matrix["true_retire"] + matrix["true_keep"]
        assert correct == 10, f"backtest moved: {correct}/12"

    def test_gsm8k_is_the_only_one_on_the_wrong_side(self):
        outcomes = run_retirement_test()
        weakest_kept = min(o.score for o in outcomes if o.label == "replacement")
        overlapping = sorted(
            o.name for o in outcomes if o.label == "retired" and o.score > weakest_kept
        )
        assert overlapping == ["GSM8K"], overlapping

    def test_separation_is_still_lost(self):
        """
        Improved from -20.6 to -10.3 and still a failure. A ten-point
        gap must not be described anywhere as close.
        """
        clean, gap = separation(run_retirement_test())
        assert not clean
        assert -15.0 < gap < -5.0, gap

    def test_specificity_no_longer_affects_the_backtest_at_all(self):
        """
        The mechanical consequence of the split, pinned: relevance is not
        in the score, so changing any rubric dimension of any of the
        twelve cannot move this result. The sensitivity analysis that
        used to be needed here is now vacuous by construction.
        """
        from dataclasses import replace

        import fetch_benchmarks as fb

        real = fb.find_benchmark
        baseline = confusion(run_retirement_test())
        try:
            for name in ("MuSR", "GSM8K", "MMLU-Pro"):
                dims = list(real(name).specificity_dimensions)
                for i in range(5):
                    for delta in (-1, 1):
                        if not 0 <= dims[i] + delta <= 2:
                            continue
                        swapped = tuple(dims[:i] + [dims[i] + delta] + dims[i + 1:])

                        def patched(label, _n=name, _d=swapped):
                            b = real(label)
                            if b is not None and b.name == _n:
                                return replace(b, specificity_dimensions=_d)
                            return b

                        fb.find_benchmark = patched
                        import backtest

                        backtest.find_benchmark = patched
                        assert confusion(run_retirement_test()) == baseline
        finally:
            fb.find_benchmark = real
            import backtest

            backtest.find_benchmark = real

    def test_replacements_have_since_declined(self):
        """The trajectory claim: 2024's harder set aged too."""
        for name in REPLACEMENTS:
            benchmark = find_benchmark(name)
            then = score_benchmark(benchmark, as_of=CUTOFF).trust_score
            now = score_benchmark(benchmark).trust_score
            assert now < then, f"{name} did not decline"


class TestScoringIsTimeAware:
    def test_freshness_is_measured_to_the_cutoff(self):
        mmlu = find_benchmark("MMLU")
        then = {f.name: f for f in score_benchmark(mmlu, as_of=CUTOFF).factors}
        now = {f.name: f for f in score_benchmark(mmlu).factors}
        assert then["freshness"].value > now["freshness"].value

    def test_saturation_uses_only_models_of_the_era(self):
        gpqa = score_benchmark(find_benchmark("GPQA Diamond"), as_of=CUTOFF)
        today = score_benchmark(find_benchmark("GPQA Diamond"))
        assert gpqa.models_measured < today.models_measured
        # GPQA was barely touched in mid-2024 and looks far healthier then.
        assert gpqa.trust_score > today.trust_score

    def test_scoring_without_as_of_is_unchanged(self):
        """Time travel must not alter normal scoring."""
        for name in ("MMLU", "SWE-Bench Verified", "MirrorCode"):
            benchmark = find_benchmark(name)
            assert score_benchmark(benchmark).trust_score == pytest.approx(
                score_benchmark(benchmark, as_of=None).trust_score
            )


class TestSweBenchFloorIsNotVisibleInThePast:
    """
    SWE-Bench Verified's item_error_rate is a floor derived from an audit
    published 2026-02-23. A backtest run at 2024-06-01 must not see it —
    and the benchmark did not even exist then (released 2024-08-13).
    """

    def test_the_audit_postdates_the_cutoff(self):
        swe = find_benchmark("SWE-Bench Verified")
        assert swe.evidence_dates["item_error_rate"] == "2026-02-23"
        assert not swe.known_at("item_error_rate", CUTOFF)

    def test_the_contamination_flag_from_the_same_post_is_also_invisible(self):
        """
        Both findings come from the 2026-02-23 post. Neither may reach a
        2024 scoring run — the benchmark did not exist and the audit was
        20 months away.
        """
        swe = find_benchmark("SWE-Bench Verified")
        assert swe.contamination_flagged
        assert swe.evidence_dates["contamination_flagged"] == "2026-02-23"
        assert not swe.known_at("contamination_flagged", CUTOFF)

        then = score_benchmark(swe, as_of=CUTOFF)
        assert not any("contamination" in p for p in then.penalties), then.penalties
        now = score_benchmark(swe)
        assert any("contamination" in p for p in now.penalties), now.penalties

    def test_flagging_contamination_did_not_move_the_2024_score(self):
        """The same property the item_error_rate revision had to satisfy."""
        from dataclasses import replace

        swe = find_benchmark("SWE-Bench Verified")
        unflagged = replace(swe, contamination_flagged=False)
        assert score_benchmark(unflagged, as_of=CUTOFF).trust_score == (
            score_benchmark(swe, as_of=CUTOFF).trust_score
        )

    def test_no_rate_or_effect_is_claimed(self):
        """The post quantifies neither; inventing one would be worse than coarse."""
        swe = find_benchmark("SWE-Bench Verified")
        assert swe.contamination_rate is None
        assert swe.contamination_effect is None

    def test_no_item_quality_penalty_is_applied_at_the_cutoff(self):
        then = score_benchmark(find_benchmark("SWE-Bench Verified"), as_of=CUTOFF)
        assert not any("mislabelled" in p for p in then.penalties), then.penalties

    def test_the_penalty_is_applied_today(self):
        now = score_benchmark(find_benchmark("SWE-Bench Verified"))
        assert any("mislabelled" in p for p in now.penalties), now.penalties

    def test_raising_the_floor_did_not_move_the_2024_score(self):
        """
        The revision must be invisible to the backtest entirely. This is the
        property that keeps the June 2024 result honest: evidence published
        in 2026 cannot change what the scorer would have said in 2024.
        """
        then = score_benchmark(find_benchmark("SWE-Bench Verified"), as_of=CUTOFF)
        # Recompute with the old value to prove the cutoff score is identical.
        from dataclasses import replace

        old = replace(find_benchmark("SWE-Bench Verified"), item_error_rate=0.10)
        assert score_benchmark(old, as_of=CUTOFF).trust_score == then.trust_score
