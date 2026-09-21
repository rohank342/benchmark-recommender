"""
fetch_benchmark_scores.py
=========================
Pulls per-model score distributions for benchmarks Epoch's export doesn't
cover, so their saturation can be measured rather than asserted.

Without this, four benchmarks — HumanEval, MMLU-Pro, TruthfulQA and
LiveCodeBench — were scored purely from curated flags. HumanEval is the
project's headline example of a benchmark that stopped discriminating,
and the claim rested on citations rather than on a distribution anyone
could check. That's the gap this closes.

Sources:

  HF Open LLM Leaderboard v2 (open-llm-leaderboard/contents)
      4,500+ models on MMLU-Pro, BBH, GPQA, MATH Lvl 5, IFEval, MuSR.
  HF Open LLM Leaderboard v1 (open-llm-leaderboard-old/contents)
      7,200+ models on ARC, HellaSwag, MMLU, TruthfulQA, Winogrande,
      GSM8K — the set retired in June 2024 for saturation.
  EvalPlus (evalplus.github.io/results.json)
      125 models on HumanEval / HumanEval+ / MBPP / MBPP+.

Both leaderboards carry a `Flagged` column marking models the
maintainers identified as contaminated or otherwise broken. Those rows
are dropped: they cluster near the top, which is exactly where
saturation is measured, so leaving them in would inflate every reading.

Run standalone to refresh:

    python fetch_benchmark_scores.py

Writes data/benchmark_scores/<benchmark key>__<source>.csv. Those files
are committed, so the measurements are reproducible without network
access and a reviewer can check the distribution behind any score.
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

import requests

DATA_DIR = Path(__file__).parent / "data"
SCORES_DIR = DATA_DIR / "benchmark_scores"

OPEN_LLM_V2_DATASET = "open-llm-leaderboard/contents"
OPEN_LLM_V1_DATASET = "open-llm-leaderboard-old/contents"
EVALPLUS_RESULTS_URL = "https://evalplus.github.io/results.json"

# Leaderboard column -> benchmark key in fetch_benchmarks.BENCHMARK_CATALOG.
OPEN_LLM_V2_COLUMNS = {
    "MMLU-PRO": "mmlu_pro",
    "BBH": "bbh",
    "GPQA": "gpqa_diamond",
    "MATH Lvl 5": "math_level_5",
}
OPEN_LLM_V1_COLUMNS = {
    "TruthfulQA": "truthfulqa",
    "MMLU": "mmlu",
    "ARC": "arc",
    "HellaSwag": "hellaswag",
}


@dataclass
class ScoreSet:
    benchmark_key: str
    source: str
    rows: list[tuple[str, float]]  # (model name, score 0-1)

    @property
    def path(self) -> Path:
        return SCORES_DIR / f"{self.benchmark_key}__{self.source}.csv"

    def save(self) -> Path:
        SCORES_DIR.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(["model", "score"])
            writer.writerows((name, f"{score:.6f}") for name, score in self.rows)
        return self.path


def _load_leaderboard_frame(dataset: str):
    """Download one leaderboard's parquet table."""
    import pandas as pd
    from huggingface_hub import HfApi, hf_hub_download

    api = HfApi()
    parquet_files = [
        sibling.rfilename
        for sibling in (api.dataset_info(dataset).siblings or [])
        if sibling.rfilename.endswith(".parquet")
    ]
    if not parquet_files:
        raise RuntimeError(f"No parquet file in {dataset}")
    return pd.read_parquet(hf_hub_download(dataset, parquet_files[0], repo_type="dataset"))


def _from_leaderboard(dataset: str, columns: dict[str, str], source: str) -> list[ScoreSet]:
    """
    Turn one leaderboard table into per-benchmark score sets.

    Scores are reported 0-100 and converted to fractions. Models the
    leaderboard flagged (contamination, broken configs) are dropped — they
    congregate at the top of the table, and the top is where saturation is
    measured.
    """
    frame = _load_leaderboard_frame(dataset)
    total = len(frame)
    if "Flagged" in frame.columns:
        flagged = frame["Flagged"].fillna(False).astype(bool)
        # In the archived v1 table this column is True for every row — a
        # property of the archive, not a judgement about each model. A
        # column with no variance can't identify anything, so only filter
        # when it actually separates models.
        if 0 < flagged.sum() < len(frame):
            frame = frame[~flagged]
        else:
            print(f"  {dataset}: 'Flagged' is uniform ({flagged.all()}) — not filtering on it")
    dropped = total - len(frame)
    print(f"  {dataset}: {total} models, {dropped} flagged and dropped")

    name_column = "fullname" if "fullname" in frame.columns else "eval_name"
    sets = []
    for column, benchmark_key in columns.items():
        if column not in frame.columns:
            print(f"    ! column {column!r} missing — skipping {benchmark_key}")
            continue
        subset = frame[[name_column, column]].dropna()
        rows = [
            (str(name), float(value) / 100.0)
            for name, value in subset.itertuples(index=False)
            if 0.0 <= float(value) <= 100.0
        ]
        if rows:
            sets.append(ScoreSet(benchmark_key, source, rows))
            print(f"    {benchmark_key:<16} {len(rows)} scores")
    return sets


def fetch_open_llm_v2() -> list[ScoreSet]:
    return _from_leaderboard(OPEN_LLM_V2_DATASET, OPEN_LLM_V2_COLUMNS, "open_llm_leaderboard_v2")


def fetch_open_llm_v1() -> list[ScoreSet]:
    return _from_leaderboard(OPEN_LLM_V1_DATASET, OPEN_LLM_V1_COLUMNS, "open_llm_leaderboard_v1")


def fetch_evalplus(timeout: int = 30) -> list[ScoreSet]:
    """
    EvalPlus publishes greedy-decoding pass@1 for HumanEval and its
    HumanEval+ variant (extra tests, same problems). Both are kept: the
    gap between them is itself evidence about how much the original's
    test coverage was letting through.
    """
    response = requests.get(EVALPLUS_RESULTS_URL, timeout=timeout)
    response.raise_for_status()
    payload = response.json()

    humaneval: list[tuple[str, float]] = []
    humaneval_plus: list[tuple[str, float]] = []
    for model, entry in payload.items():
        scores = (entry or {}).get("pass@1") or {}
        if isinstance(scores.get("humaneval"), (int, float)):
            humaneval.append((model, float(scores["humaneval"]) / 100.0))
        if isinstance(scores.get("humaneval+"), (int, float)):
            humaneval_plus.append((model, float(scores["humaneval+"]) / 100.0))

    print(f"  evalplus: {len(humaneval)} HumanEval, {len(humaneval_plus)} HumanEval+ scores")
    sets = []
    if humaneval:
        sets.append(ScoreSet("humaneval", "evalplus", humaneval))
    if humaneval_plus:
        sets.append(ScoreSet("humaneval_plus", "evalplus", humaneval_plus))
    return sets


SOURCES: tuple[tuple[str, Callable[[], list[ScoreSet]]], ...] = (
    ("HF Open LLM Leaderboard v2", fetch_open_llm_v2),
    ("HF Open LLM Leaderboard v1", fetch_open_llm_v1),
    ("EvalPlus", fetch_evalplus),
)

########################################################################
# CURATE(you): LiveCodeBench has no fetchable score export. Its
# leaderboard (https://livecodebench.github.io) inlines results in a
# bundled JS file with no JSON endpoint, and the HF dataset ships
# problems rather than model scores. Until a source turns up, its
# saturation stays asserted rather than measured — which the UI reports
# as "unknown (no score data)". If you find an export, add a fetcher
# above and it will be picked up automatically.
########################################################################


def main() -> None:
    all_sets: list[ScoreSet] = []
    for label, fetcher in SOURCES:
        print(f"{label}:")
        try:
            all_sets.extend(fetcher())
        except Exception as exc:  # one dead source shouldn't stop the rest
            print(f"  FAILED: {type(exc).__name__}: {exc}")

    for score_set in all_sets:
        score_set.save()
    print(f"\nSaved {len(all_sets)} score sets to {SCORES_DIR}")


if __name__ == "__main__":
    main()
