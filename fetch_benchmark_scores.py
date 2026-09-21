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
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

import requests

DATA_DIR = Path(__file__).parent / "data"
SCORES_DIR = DATA_DIR / "benchmark_scores"
# Per-set metadata: which column was read, whether it is baseline-normalized,
# and the random baseline. Without this a reader cannot tell a raw accuracy
# from a normalized one, and the two are not comparable — see below.
MANIFEST_PATH = SCORES_DIR / "manifest.json"

OPEN_LLM_V2_DATASET = "open-llm-leaderboard/contents"
OPEN_LLM_V1_DATASET = "open-llm-leaderboard-old/contents"
EVALPLUS_RESULTS_URL = "https://evalplus.github.io/results.json"

# Leaderboard column -> benchmark key in fetch_benchmarks.BENCHMARK_CATALOG.
#
# v2 publishes each benchmark twice: "<name> Raw" is the accuracy, "<name>"
# is rescaled so the random baseline sits at 0. The RAW columns are the ones
# to read. An earlier version of this file took the normalized ones, which
# made GPQA look like models were scoring 1-5% (raw 0.26 -> normalized 1.2,
# because (0.26-0.25)/0.75 is tiny) and made cross-source comparison against
# Epoch measure the rescaling rather than any disagreement.
OPEN_LLM_V2_COLUMNS = {
    "MMLU-PRO Raw": "mmlu_pro",
    "BBH Raw": "bbh",
    "GPQA Raw": "gpqa_diamond",
    "MATH Lvl 5 Raw": "math_level_5",
}
# v1 has no raw/normalized split, but it is not uniform either: ARC and
# HellaSwag were reported as normalized accuracy (acc_norm) while MMLU and
# TruthfulQA were plain accuracy. Recorded per set in the manifest so a
# reader can see which is which.
OPEN_LLM_V1_COLUMNS = {
    "TruthfulQA": "truthfulqa",
    "MMLU": "mmlu",
    "ARC": "arc",
    "HellaSwag": "hellaswag",
}
# Two different normalizations are in play, and calling both "normalized"
# would hide the difference:
#   "baseline" — v2 rescales so random chance sits at 0. GPQA raw 0.26
#                becomes 1.2 because (0.26-0.25)/0.75 is tiny.
#   "length"   — v1 reported ARC and HellaSwag as acc_norm, accuracy
#                normalized by the byte length of the answer choices.
#   "none"     — plain accuracy, comparable with Epoch's numbers.
# Only "none" is comparable across sources without further work.
V1_NORMALIZATION = {"ARC": "length", "HellaSwag": "length"}
# CURATE(you): the acc/acc_norm split is from the v1 leaderboard's task
# config. Worth re-verifying against the archived "About" page if a
# comparison ever hinges on it.

# Random baselines, taken from Epoch's benchmark_metadata.csv so that the two
# sources agree on the usable score range. Not invented here.
RANDOM_BASELINES = {
    "mmlu": 0.25,
    "arc": 0.25,
    "hellaswag": 0.25,
    "bbh": 0.25,
    "gpqa_diamond": 0.25,
    "math_level_5": 0.0,
    "truthfulqa": 0.0,  # generative/MC2 scoring, no clean chance baseline
    "mmlu_pro": 0.1,  # ten options
    "humaneval": 0.0,
    "humaneval_plus": 0.0,
}


@dataclass
class ScoreSet:
    benchmark_key: str
    source: str
    # (model name, score 0-1, model date or "" when the source has none).
    # The date is what makes the backtest possible: scoring a benchmark
    # "as of" a past date means using only models that existed then.
    rows: list[tuple[str, float, str]] = field(default_factory=list)
    column: str = ""  # the column this came from, verbatim
    normalization: str = "none"  # "none" | "baseline" | "length"

    @property
    def random_baseline(self) -> float:
        # A baseline-normalized column already has chance removed, so its
        # usable range starts at 0 whatever the benchmark's chance level.
        if self.normalization == "baseline":
            return 0.0
        return RANDOM_BASELINES.get(self.benchmark_key, 0.0)

    @property
    def manifest_entry(self) -> dict:
        return {
            "benchmark_key": self.benchmark_key,
            "source": self.source,
            "column": self.column,
            "normalization": self.normalization,
            "random_baseline": self.random_baseline,
            "ceiling": 1.0,
            "models": len(self.rows),
            "dated_models": sum(1 for row in self.rows if row[2]),
        }

    @property
    def path(self) -> Path:
        return SCORES_DIR / f"{self.benchmark_key}__{self.source}.csv"

    def save(self) -> Path:
        SCORES_DIR.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(["model", "score", "date"])
            writer.writerows(
                (name, f"{score:.6f}", date or "") for name, score, date in self.rows
            )
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


def _from_leaderboard(
    dataset: str,
    columns: dict[str, str],
    source: str,
    normalization: Optional[dict[str, str]] = None,
) -> list[ScoreSet]:
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
    # v1 records a submission date; v2 records when the model was uploaded
    # to the Hub, which is closer to "when did this model exist".
    date_column = next(
        (c for c in ("Upload To Hub Date", "date", "Submission Date") if c in frame.columns),
        None,
    )
    if date_column is None:
        print(f"  ! {dataset} has no date column — sets from it can't be time-filtered")
    sets = []
    for column, benchmark_key in columns.items():
        if column not in frame.columns:
            print(f"    ! column {column!r} missing — skipping {benchmark_key}")
            continue
        wanted = [name_column, column] + ([date_column] if date_column else [])
        subset = frame[wanted].dropna(subset=[name_column, column])
        # Raw columns are already fractions (0.26); normalized ones are
        # percentages (1.23). Detect rather than assume, so a change in the
        # leaderboard's units doesn't silently divide everything by 100.
        values = subset[column].astype(float)
        looks_fractional = float(values.max()) <= 1.0
        divisor = 1.0 if looks_fractional else 100.0

        rows = []
        for record in subset.itertuples(index=False):
            name, value = record[0], record[1]
            date = str(record[2])[:10] if date_column and len(record) > 2 else ""
            score = float(value) / divisor
            if 0.0 <= score <= 1.0:
                rows.append((str(name), score, "" if date in ("nan", "NaT") else date))

        if rows:
            # Stated per column, not guessed from magnitude: v1 reports
            # percentages that are still plain accuracy, so "not fractional"
            # says nothing about whether a score has been normalized.
            kind = (normalization or {}).get(column, "none")
            sets.append(
                ScoreSet(benchmark_key, source, rows, column=column, normalization=kind)
            )
            print(
                f"    {benchmark_key:<16} {len(rows)} scores from {column!r} "
                f"(normalization: {kind})"
            )
    return sets


def fetch_open_llm_v2() -> list[ScoreSet]:
    return _from_leaderboard(OPEN_LLM_V2_DATASET, OPEN_LLM_V2_COLUMNS, "open_llm_leaderboard_v2")


def fetch_open_llm_v1() -> list[ScoreSet]:
    return _from_leaderboard(
        OPEN_LLM_V1_DATASET,
        OPEN_LLM_V1_COLUMNS,
        "open_llm_leaderboard_v1",
        normalization=V1_NORMALIZATION,
    )


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
        # EvalPlus publishes no per-model dates, so these sets cannot be
        # time-filtered and are excluded from any as-of scoring.
        if isinstance(scores.get("humaneval"), (int, float)):
            humaneval.append((model, float(scores["humaneval"]) / 100.0, ""))
        if isinstance(scores.get("humaneval+"), (int, float)):
            humaneval_plus.append((model, float(scores["humaneval+"]) / 100.0, ""))

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

    manifest = {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "sets": {
            f"{s.benchmark_key}__{s.source}": s.manifest_entry for s in all_sets
        },
    }
    SCORES_DIR.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2))
    print(f"\nSaved {len(all_sets)} score sets + manifest to {SCORES_DIR}")


if __name__ == "__main__":
    main()
