import json

from enrich_scores import (
    ExternalScoreIndex,
    build_external_index,
    load_artificial_analysis,
    load_epoch_ai,
)


def _write_aa_cache(tmp_path, models):
    path = tmp_path / "artificial_analysis.json"
    path.write_text(json.dumps({"fetched_at": "2026-09-01T00:00:00+00:00", "models": models}))
    return path


class TestArtificialAnalysis:
    def test_models_are_indexed_by_match_key(self, tmp_path):
        path = _write_aa_cache(
            tmp_path,
            [
                {
                    "name": "Qwen2.5 Coder 7B Instruct",
                    "slug": "qwen2-5-coder-7b-instruct",
                    "release_date": "2024-11-12",
                    "evaluations": {"artificial_analysis_coding_index": 24.5},
                }
            ],
        )
        index = ExternalScoreIndex()
        load_artificial_analysis(index, path)

        scores = index.lookup("Qwen/Qwen2.5-Coder-7B-Instruct")
        assert len(scores) == 1
        assert scores[0].score == 24.5
        assert scores[0].source == "artificial_analysis"
        assert scores[0].reported_date == "2024-11-12"

    def test_coding_index_is_used_not_general_intelligence(self, tmp_path):
        path = _write_aa_cache(
            tmp_path,
            [
                {
                    "name": "Some Coder 7B",
                    "evaluations": {
                        "artificial_analysis_intelligence_index": 24.5,
                        "artificial_analysis_coding_index": 42.0,
                    },
                }
            ],
        )
        index = ExternalScoreIndex()
        load_artificial_analysis(index, path)
        score = index.lookup("org/Some-Coder-7B")[0]
        assert score.score == 42.0
        assert score.benchmark_name == "artificial_analysis_coding_index"

    def test_general_intelligence_alone_is_not_a_coding_score(self, tmp_path):
        """The two indices are on different scales — never substitute one."""
        path = _write_aa_cache(
            tmp_path,
            [
                {
                    "name": "General Model 7B",
                    "evaluations": {"artificial_analysis_intelligence_index": 24.5},
                }
            ],
        )
        index = ExternalScoreIndex()
        load_artificial_analysis(index, path)
        assert index.lookup("org/General-Model-7B") == []

    def test_huggingface_url_wins_over_name_when_present(self, tmp_path):
        """Pro tier gives a canonical repo URL — trust it over the label."""
        path = _write_aa_cache(
            tmp_path,
            [
                {
                    "name": "Marketing Name That Matches Nothing",
                    "huggingface_url": "https://huggingface.co/Qwen/Qwen2.5-Coder-7B-Instruct",
                    "evaluations": {"artificial_analysis_coding_index": 42.0},
                }
            ],
        )
        index = ExternalScoreIndex()
        load_artificial_analysis(index, path)
        assert index.lookup("Qwen/Qwen2.5-Coder-7B-Instruct")

    def test_models_without_scores_are_skipped(self, tmp_path):
        path = _write_aa_cache(tmp_path, [{"name": "No Evals 7B", "evaluations": {}}])
        index = ExternalScoreIndex()
        load_artificial_analysis(index, path)
        assert index.lookup("org/No-Evals-7B") == []

    def test_missing_cache_warns_rather_than_raising(self, tmp_path):
        index = ExternalScoreIndex()
        load_artificial_analysis(index, tmp_path / "absent.json")
        assert index.sources_loaded == []
        assert any("No Artificial Analysis cache" in w for w in index.warnings)


class TestEpochCsv:
    def _write(self, tmp_path, text):
        path = tmp_path / "epoch_benchmarks.csv"
        path.write_text(text)
        return path

    def test_code_rows_are_indexed_and_other_benchmarks_dropped(self, tmp_path):
        path = self._write(
            tmp_path,
            "model,task,score,date\n"
            "Qwen2.5 Coder 7B Instruct,MirrorCode,0.42,2025-08-01\n"
            "Qwen2.5 Coder 7B Instruct,FrontierMath,0.11,2025-08-01\n",
        )
        index = ExternalScoreIndex()
        load_epoch_ai(index, path)

        scores = index.lookup("Qwen/Qwen2.5-Coder-7B-Instruct")
        assert [s.benchmark_name for s in scores] == ["MirrorCode"]
        assert scores[0].score_scale == "0-1"

    def test_percentage_scale_is_detected_per_file(self, tmp_path):
        path = self._write(
            tmp_path, "model,task,score,date\nSome Coder 7B,HumanEval,68.4,2025-08-01\n"
        )
        index = ExternalScoreIndex()
        load_epoch_ai(index, path)
        assert index.lookup("org/Some-Coder-7B")[0].score_scale == "0-100"

    def test_unrecognized_columns_are_reported(self, tmp_path):
        path = self._write(tmp_path, "col_a,col_b\nx,y\n")
        index = ExternalScoreIndex()
        load_epoch_ai(index, path)
        assert any("unrecognized columns" in w for w in index.warnings)

    def test_unparseable_scores_are_skipped(self, tmp_path):
        path = self._write(
            tmp_path,
            "model,task,score,date\n"
            "A Coder 7B,HumanEval,n/a,2025-08-01\n"
            "B Coder 7B,HumanEval,0.5,2025-08-01\n",
        )
        index = ExternalScoreIndex()
        load_epoch_ai(index, path)
        assert index.lookup("org/A-Coder-7B") == []
        assert index.lookup("org/B-Coder-7B")


def test_build_index_without_any_sources_is_empty_not_fatal(tmp_path):
    index = build_external_index(tmp_path / "none.json", tmp_path / "none.csv")
    assert index.by_key == {}
    assert len(index.warnings) == 2
