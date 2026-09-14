"""
enrich_scores.py
=================
Cross-references benchmark scores that aren't (reliably) present in a
model's Hugging Face card metadata, by pulling from external sources:

  - Artificial Analysis (https://artificialanalysis.ai) — independent
    third-party benchmark runs + quality/price/speed tradeoffs.
  - Epoch AI (https://epoch.ai) — benchmark reliability / contamination
    risk flags, used here to seed the "trust discount" in scoring.py.

########################################################################
# TODO(you): PLUG IN REAL API KEYS / ENDPOINTS HERE
########################################################################
Both integrations below are STUBS that return mock data so the rest of
the pipeline (scoring, filtering, the Gradio app) is runnable end-to-end
today. To wire up the real thing:

  1. Get an Artificial Analysis API key and set it as the
     ARTIFICIAL_ANALYSIS_API_KEY environment variable.
  2. Get Epoch AI access (their benchmarking hub / data exports) and set
     EPOCH_AI_API_KEY (or point EPOCH_AI_DATA_PATH at a downloaded
     dataset export if they don't offer a live API).
  3. Replace the bodies of `_fetch_from_artificial_analysis` and
     `_fetch_from_epoch_ai` below with real HTTP calls (see the `requests`
     import already included for you) or dataset lookups.
  4. Keep the return shape of `fetch_external_score` the same so
     scoring.py doesn't need to change.
########################################################################
"""

from __future__ import annotations

import os
import random
from dataclasses import dataclass, field
from typing import Any, Optional

import requests  # noqa: F401  (kept here for when the real API calls are wired in)

# TODO(you): set these in your environment (.env, shell profile, etc.)
ARTIFICIAL_ANALYSIS_API_KEY = os.environ.get("ARTIFICIAL_ANALYSIS_API_KEY")
EPOCH_AI_API_KEY = os.environ.get("EPOCH_AI_API_KEY")

ARTIFICIAL_ANALYSIS_BASE_URL = "https://artificialanalysis.ai/api/v1"  # TODO(you): confirm real base URL
EPOCH_AI_BASE_URL = "https://epoch.ai/api/v1"  # TODO(you): confirm real base URL


@dataclass
class ExternalScore:
    """Normalized shape for one external benchmark data point."""

    source: str  # e.g. "artificial_analysis", "epoch_ai"
    benchmark_name: str  # e.g. "HumanEval", "MBPP", "LiveCodeBench"
    score: Optional[float]  # raw reported score (whatever scale the source uses)
    score_scale: str  # e.g. "0-100", "0-1" — scoring.py needs this to normalize
    reported_date: Optional[str]  # ISO date the benchmark run was reported/updated
    contamination_flag: bool = False  # Epoch-style "possible train/test leakage" flag
    notes: str = ""


def _fetch_from_artificial_analysis(model_name: str) -> list[ExternalScore]:
    """
    STUB — replace with a real call to the Artificial Analysis API once
    ARTIFICIAL_ANALYSIS_API_KEY is set.

    Real implementation sketch:

        resp = requests.get(
            f"{ARTIFICIAL_ANALYSIS_BASE_URL}/models/{model_name}/benchmarks",
            headers={"Authorization": f"Bearer {ARTIFICIAL_ANALYSIS_API_KEY}"},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        return [ExternalScore(source="artificial_analysis", ...) for row in data]
    """
    # --- MOCK DATA (placeholder until real API is wired up) ---
    rng = random.Random(model_name)  # deterministic mock per model, not real perf data
    mock_score = round(rng.uniform(30, 85), 1)
    return [
        ExternalScore(
            source="artificial_analysis",
            benchmark_name="HumanEval (mock)",
            score=mock_score,
            score_scale="0-100",
            reported_date="2025-06-01",  # TODO(you): real reported date from API
            contamination_flag=False,
            notes="MOCK DATA — wire up ARTIFICIAL_ANALYSIS_API_KEY for real scores.",
        )
    ]


def _fetch_from_epoch_ai(model_name: str) -> list[ExternalScore]:
    """
    STUB — replace with a real call/lookup against Epoch AI's benchmarking
    data once EPOCH_AI_API_KEY (or a local data export) is available.

    Epoch AI is primarily useful here for *reliability signals* — e.g.
    flags for likely benchmark contamination or staleness — which feed
    the "trust discount" in scoring.py, not just another raw score.
    """
    # --- MOCK DATA (placeholder until real API is wired up) ---
    rng = random.Random(model_name + "-epoch")
    mock_score = round(rng.uniform(30, 85), 1)
    mock_contamination = rng.random() < 0.15  # ~15% of mock models flagged, just for demo variety
    return [
        ExternalScore(
            source="epoch_ai",
            benchmark_name="LiveCodeBench (mock)",
            score=mock_score,
            score_scale="0-100",
            reported_date="2025-03-15",  # TODO(you): real reported date from API/export
            contamination_flag=mock_contamination,
            notes="MOCK DATA — wire up EPOCH_AI_API_KEY / data export for real scores.",
        )
    ]


def fetch_external_score(model_name: str) -> list[ExternalScore]:
    """
    Public entry point used by scoring.py. Aggregates every external
    source into one list of ExternalScore records for a given model.

    ######################################################################
    # TODO(you): this currently returns MOCK DATA from both sources.
    # Once ARTIFICIAL_ANALYSIS_API_KEY / EPOCH_AI_API_KEY are set and the
    # two _fetch_from_* functions above are wired to real endpoints, this
    # function needs no changes — it just aggregates their real outputs.
    ######################################################################
    """
    results: list[ExternalScore] = []
    results.extend(_fetch_from_artificial_analysis(model_name))
    results.extend(_fetch_from_epoch_ai(model_name))
    return results


if __name__ == "__main__":
    # Quick manual smoke test.
    sample = fetch_external_score("deepseek-ai/deepseek-coder-6.7b-instruct")
    for s in sample:
        print(s)
