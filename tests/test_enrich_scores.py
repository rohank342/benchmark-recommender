import json

import pytest

from enrich_scores import (
    ExternalScoreIndex,
    build_external_index,
    epoch_catalog_targets,
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


class TestEpochExport:
    """Epoch ships a directory: metadata indexing one CSV per benchmark."""

    def _write_export(self, tmp_path, metadata_rows, files):
        directory = tmp_path / "epoch_benchmarks"
        directory.mkdir()
        header = "benchmark,in_eci,source_file,score_column,scale,random_baseline,score_ceiling,release_date,superseded_by\n"
        (directory / "benchmark_metadata.csv").write_text(header + "".join(metadata_rows))
        for name, text in files.items():
            (directory / name).write_text(text)
        return directory

    def test_code_benchmarks_are_indexed(self, tmp_path):
        directory = self._write_export(
            tmp_path,
            ["MirrorCode,True,mirrorcode.csv,Best score (across scorers),1.0,0.0,1.0,2026-06-26,\n"],
            {
                "mirrorcode.csv": "Model version,Best score (across scorers),Date of evaluation,Organization\n"
                "Qwen2.5 Coder Instruct 7B,0.42,2026-07-01,Alibaba\n"
            },
        )
        index = ExternalScoreIndex()
        load_epoch_ai(index, directory)

        scores = index.lookup("Qwen/Qwen2.5-Coder-7B-Instruct")
        assert len(scores) == 1
        assert scores[0].score == 0.42
        assert scores[0].benchmark_name == "MirrorCode"
        assert scores[0].reported_date == "2026-07-01"

    def test_non_code_benchmarks_are_ignored(self, tmp_path):
        directory = self._write_export(
            tmp_path,
            ["FrontierMath,True,frontiermath.csv,Best score (across scorers),1.0,0.0,1.0,2024-11-01,\n"],
            {
                "frontiermath.csv": "Model version,Best score (across scorers),Date of evaluation\n"
                "Some Coder 7B,0.9,2026-07-01\n"
            },
        )
        index = ExternalScoreIndex()
        load_epoch_ai(index, directory)
        assert index.lookup("org/Some-Coder-7B") == []

    def test_percentage_columns_are_rescaled_by_the_metadata(self, tmp_path):
        """Aider polyglot is a percentage; `scale` converts it to a fraction."""
        directory = self._write_export(
            tmp_path,
            ["Aider polyglot,True,aider.csv,Percent correct,0.01,0.0,1.0,2024-12-21,\n"],
            {"aider.csv": "Model version,Percent correct,Date of evaluation\nSome Coder 7B,41.8,2026-07-01\n"},
        )
        index = ExternalScoreIndex()
        load_epoch_ai(index, directory)
        score = index.lookup("org/Some-Coder-7B")[0]
        assert score.score == pytest.approx(0.418)
        assert score.score_scale == "0-1"

    def test_missing_export_warns_rather_than_raising(self, tmp_path):
        index = ExternalScoreIndex()
        load_epoch_ai(index, tmp_path / "absent")
        assert index.sources_loaded == []
        assert any("No Epoch AI export" in w for w in index.warnings)

    def test_catalog_targets_come_from_code_benchmarks_only(self, tmp_path):
        directory = self._write_export(
            tmp_path,
            [
                "MirrorCode,True,mirrorcode.csv,Best score (across scorers),1.0,0.0,1.0,2026-06-26,\n",
                "FrontierMath,True,frontiermath.csv,Best score (across scorers),1.0,0.0,1.0,2024-11-01,\n",
            ],
            {
                "mirrorcode.csv": "Model version,Best score (across scorers),Date of evaluation,Organization\n"
                "DeepSeek-V3,0.42,2026-07-01,DeepSeek\n",
                "frontiermath.csv": "Model version,Best score (across scorers),Date of evaluation\n"
                "Maths Only Model,0.9,2026-07-01\n",
            },
        )
        targets = epoch_catalog_targets(directory)
        labels = [label for _, label, _ in targets]
        assert labels == ["DeepSeek-V3"]
        assert targets[0][2] == "DeepSeek"


def test_build_index_without_any_sources_is_empty_not_fatal(tmp_path):
    index = build_external_index(tmp_path / "none.json", tmp_path / "none")
    assert index.by_key == {}
    assert len(index.warnings) == 2
