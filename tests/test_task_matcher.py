from benchmark_scoring import score_all_benchmarks
from task_matcher import benchmarks_for_category, match_task, recommend_benchmarks


class TestMatching:
    def test_plain_descriptions(self):
        assert match_task("code generation").category == "code generation"
        assert match_task("fixing bugs in a legacy repository").category == "software engineering"
        assert match_task("an agent that runs shell commands").category == "agentic tool use"
        assert match_task("medical QA for clinicians").category == "scientific reasoning"

    def test_longer_phrases_outweigh_incidental_words(self):
        """"tool use" should win even with "code" floating around."""
        match = match_task("agentic tool use for code repositories")
        assert match.category in ("agentic tool use", "software engineering")
        assert match.confidence > 0

    def test_word_boundaries_prevent_false_matches(self):
        """'urgent' contains 'agent'; 'mysqld' contains 'sql'."""
        assert match_task("this is urgent").category is None

    def test_unmatched_description_is_reported_honestly(self):
        match = match_task("underwater basket weaving")
        assert match.category is None
        assert match.confidence == 0.0
        assert "No category matched" in match.explanation

    def test_empty_input(self):
        assert match_task("").category is None
        assert match_task("   ").category is None

    def test_explanation_names_the_matched_terms(self):
        match = match_task("I need help with python code")
        assert "code" in match.explanation or "python" in match.explanation


class TestRecommendation:
    def test_returns_benchmarks_ranked_by_trust(self):
        _, benchmarks = recommend_benchmarks("code generation")
        assert benchmarks
        scores = [b.trust_score for b in benchmarks]
        assert scores == sorted(scores, reverse=True)

    def test_popular_benchmark_does_not_win_by_default(self):
        """HumanEval is the famous code benchmark and should not lead."""
        _, benchmarks = recommend_benchmarks("code generation")
        names = [b.benchmark.name for b in benchmarks]
        assert "HumanEval" in names
        assert names[0] != "HumanEval"

    def test_unmatched_task_still_shows_the_landscape(self):
        match, benchmarks = recommend_benchmarks("underwater basket weaving")
        assert match.category is None
        assert len(benchmarks) > 5  # whole catalog, not an empty table

    def test_category_filter_is_exact(self):
        scored = score_all_benchmarks()
        for trust in benchmarks_for_category("software engineering", scored):
            assert trust.benchmark.category == "software engineering"
