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
