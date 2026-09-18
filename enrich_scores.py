"""
enrich_scores.py
=================
Cross-references benchmark scores that aren't reliably present in a
model's Hugging Face card metadata, against external sources:

  - Artificial Analysis (https://artificialanalysis.ai) — independent
    benchmark runs. Live JSON API, key required.
  - Epoch AI (https://epoch.ai) — independent benchmark runs, from a CSV
    export you download by hand (they have no public REST API).

Both sources publish one *catalog* covering every model they track, and
neither offers per-model lookups worth making one request at a time
(Artificial Analysis' free tier allows 100 requests per 24h — fewer than
the number of models we score). So each source is loaded in bulk, cached
on disk, and indexed by match key; scoring.py then looks models up
locally via ExternalScoreIndex.

Setup:

  Artificial Analysis — create a key at https://artificialanalysis.ai/data-api
  and export it:

      export ARTIFICIAL_ANALYSIS_API_KEY=...
      python enrich_scores.py          # fetches + caches the catalog

  Epoch AI — download the benchmark CSV from
  https://epoch.ai/benchmarks/use-this-data#download-this-data and save it
  to data/epoch_benchmarks.csv. Their data is CC-BY: credit
  "Epoch AI, 'Capabilities & Benchmarking'. epoch.ai (2026)" wherever you
  display it.

Either source may be absent — the index is built from whatever is there,
and scoring degrades to fewer sources (which the trust score already
accounts for).
"""

from __future__ import annotations

import csv
import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Optional

import requests

from model_matching import key_from_huggingface_url, match_key

DATA_DIR = Path(__file__).parent / "data"
AA_CACHE_PATH = DATA_DIR / "artificial_analysis.json"
EPOCH_CSV_PATH = DATA_DIR / "epoch_benchmarks.csv"

ARTIFICIAL_ANALYSIS_API_KEY = os.environ.get("ARTIFICIAL_ANALYSIS_API_KEY")

# v2 API, authenticated with an `x-api-key` header (not Bearer).
# /language/models/free is the free tier's endpoint; paid keys can use
# /language/models, which also returns `huggingface_url` (exact repo
# matching) and per-benchmark scores instead of only headline indices.
ARTIFICIAL_ANALYSIS_BASE_URL = "https://artificialanalysis.ai/api/v2"
AA_FREE_ENDPOINT = f"{ARTIFICIAL_ANALYSIS_BASE_URL}/language/models/free"
AA_PAID_ENDPOINT = f"{ARTIFICIAL_ANALYSIS_BASE_URL}/language/models"
AA_PAGE_SIZE = 200

# The only evaluation field this project should rank on. Deliberately
# not falling back to artificial_analysis_intelligence_index: it is a
# general-capability score on a different scale (observed 3-53 across the
# catalog, against 0-82 for coding), so mixing the two into one average
# would penalize whichever models happened to be scored on the general
# index. A model without a coding index simply has no AA score here.
# Coverage cost: ~261 of 652 catalogued models carry a coding index.
AA_CODING_EVALUATION = "artificial_analysis_coding_index"

# Epoch tracks ~80 benchmarks across maths, agentic work, games, etc.
# v1 scope is code generation, so only code-relevant rows are kept.
CODE_BENCHMARK_HINTS = (
    "code",
    "swe",
    "humaneval",
    "mbpp",
    "livecodebench",
    "mirrorcode",
    "bigcodebench",
    "apps",
    "terminalbench",
    "scicode",
)

# Epoch's CSV column names aren't contractual, so accept the plausible
# spellings and fail loudly if none are present.
_EPOCH_MODEL_COLUMNS = ("model", "model_name", "ml_model", "system")
_EPOCH_BENCHMARK_COLUMNS = ("task", "benchmark", "task_path", "benchmark_name")
_EPOCH_SCORE_COLUMNS = ("score", "accuracy", "best_score", "value", "result")
_EPOCH_DATE_COLUMNS = ("date", "run_date", "publication_date", "released", "release_date")


@dataclass
class ExternalScore:
    """Normalized shape for one external benchmark data point."""

    source: str  # e.g. "artificial_analysis", "epoch_ai"
    benchmark_name: str  # e.g. "HumanEval", "MirrorCode"
    score: Optional[float]  # raw reported score (whatever scale the source uses)
    score_scale: str  # "0-100" / "0-1" — scoring.py needs this to normalize
    reported_date: Optional[str]  # ISO date this figure was reported
    matched_name: Optional[str] = None  # how the source named the model
    notes: str = ""


@dataclass
class ExternalScoreIndex:
    """External scores keyed by match key, plus what did/didn't load."""

    by_key: dict[str, list[ExternalScore]] = field(default_factory=dict)
    sources_loaded: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def lookup(self, model_id: str) -> list[ExternalScore]:
        key = match_key(model_id)
        if key is None:
            return []
        return list(self.by_key.get(key, []))

    def add(self, key: Optional[str], score: ExternalScore) -> None:
        if key is None:
            return
        self.by_key.setdefault(key, []).append(score)


# --- Artificial Analysis ---------------------------------------------


def fetch_artificial_analysis_catalog(
    api_key: Optional[str] = None,
    endpoint: str = AA_FREE_ENDPOINT,
    timeout: int = 30,
) -> list[dict[str, Any]]:
    """
    Fetch every model Artificial Analysis tracks, following pagination.
    Returns the raw model dicts; raises on HTTP errors so a bad key or an
    exhausted rate limit is visible rather than silently empty.
    """
    api_key = api_key or ARTIFICIAL_ANALYSIS_API_KEY
    if not api_key:
        raise RuntimeError(
            "ARTIFICIAL_ANALYSIS_API_KEY is not set — create a key at "
            "https://artificialanalysis.ai/data-api"
        )

    models: list[dict[str, Any]] = []
    page = 1
    while True:
        response = requests.get(
            endpoint,
            headers={"x-api-key": api_key},
            params={"page": page, "page_size": AA_PAGE_SIZE},
            timeout=timeout,
        )
        response.raise_for_status()
        payload = response.json()
        models.extend(payload.get("data") or [])

        pagination = payload.get("pagination") or {}
        total_pages = pagination.get("total_pages")
        if pagination.get("has_more") is False:
            break
        if total_pages is not None and page >= total_pages:
            break
        if not pagination:  # unpaginated response
            break
        page += 1
    return models


def save_artificial_analysis_cache(
    models: list[dict[str, Any]], path: Path = AA_CACHE_PATH
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {"fetched_at": datetime.now(timezone.utc).isoformat(), "models": models},
            indent=2,
        )
    )


def _aa_score(model: dict[str, Any]) -> tuple[Optional[str], Optional[float]]:
    """The model's coding index, or (None, None) if it doesn't have one."""
    value = (model.get("evaluations") or {}).get(AA_CODING_EVALUATION)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return AA_CODING_EVALUATION, float(value)
    return None, None


def load_artificial_analysis(
    index: ExternalScoreIndex, path: Path = AA_CACHE_PATH
) -> None:
    """Add cached Artificial Analysis scores to `index`."""
    if not path.exists():
        index.warnings.append(
            f"No Artificial Analysis cache at {path} — run `python enrich_scores.py` "
            "with ARTIFICIAL_ANALYSIS_API_KEY set."
        )
        return

    payload = json.loads(path.read_text())
    models = payload.get("models") or []
    fetched_at = payload.get("fetched_at")
    added = 0

    for model in models:
        benchmark_name, score = _aa_score(model)
        if score is None:
            continue
        name = model.get("name") or model.get("slug")
        # Pro tier gives a canonical Hub URL; free tier only gives names.
        key = key_from_huggingface_url(model.get("huggingface_url")) or match_key(name)
        index.add(
            key,
            ExternalScore(
                source="artificial_analysis",
                benchmark_name=benchmark_name,
                score=score,
                score_scale="0-100",
                # AA reports no per-evaluation date; the model's release
                # date is the closest available staleness signal.
                reported_date=model.get("release_date") or fetched_at,
                matched_name=name,
            ),
        )
        added += 1

    index.sources_loaded.append("artificial_analysis")
    if not added:
        index.warnings.append(
            f"Artificial Analysis cache at {path} held no usable evaluation scores."
        )


def artificial_analysis_catalog_targets(
    path: Path = AA_CACHE_PATH,
) -> list[tuple[str, str, Optional[str]]]:
    """
    Models Artificial Analysis has a coding score for, as
    (match key, label, crediting organization) — the input to
    fetch_models.fetch_models_for_catalog(), which locates the open-weight
    ones on the Hub. Closed models are included here and simply fail to
    resolve; that filtering belongs to the Hub lookup, not to this list.
    """
    if not path.exists():
        return []
    targets: dict[str, tuple[str, str, Optional[str]]] = {}
    for model in json.loads(path.read_text()).get("models") or []:
        _, score = _aa_score(model)
        if score is None:
            continue
        label = model.get("name") or model.get("slug")
        key = match_key(label)
        if not key:
            continue
        creator = (model.get("model_creator") or {}).get("name")
        targets[key] = (key, label, creator)
    return list(targets.values())


# --- Epoch AI ---------------------------------------------------------


def _pick_column(fieldnames: Iterable[str], candidates: tuple[str, ...]) -> Optional[str]:
    normalized = {name.strip().lower().replace(" ", "_"): name for name in fieldnames}
    for candidate in candidates:
        if candidate in normalized:
            return normalized[candidate]
    return None


def _is_code_benchmark(name: str) -> bool:
    lowered = name.lower()
    return any(hint in lowered for hint in CODE_BENCHMARK_HINTS)


def load_epoch_ai(index: ExternalScoreIndex, path: Path = EPOCH_CSV_PATH) -> None:
    """
    Add scores from a downloaded Epoch AI benchmark CSV to `index`.

    Their column names are not a published contract, so the columns are
    detected from a list of plausible spellings and an unrecognized
    header is reported rather than silently skipped.
    """
    if not path.exists():
        index.warnings.append(
            f"No Epoch AI CSV at {path} — download it from "
            "https://epoch.ai/benchmarks/use-this-data#download-this-data"
        )
        return

    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        fieldnames = reader.fieldnames or []
        model_col = _pick_column(fieldnames, _EPOCH_MODEL_COLUMNS)
        bench_col = _pick_column(fieldnames, _EPOCH_BENCHMARK_COLUMNS)
        score_col = _pick_column(fieldnames, _EPOCH_SCORE_COLUMNS)
        date_col = _pick_column(fieldnames, _EPOCH_DATE_COLUMNS)

        if not (model_col and bench_col and score_col):
            index.warnings.append(
                f"Epoch AI CSV at {path} has unrecognized columns {fieldnames!r}; "
                "update the _EPOCH_*_COLUMNS lists in enrich_scores.py."
            )
            return

        rows = []
        for row in reader:
            benchmark = (row.get(bench_col) or "").strip()
            model_name = (row.get(model_col) or "").strip()
            if not benchmark or not model_name or not _is_code_benchmark(benchmark):
                continue
            try:
                score = float((row.get(score_col) or "").strip().rstrip("%"))
            except ValueError:
                continue
            rows.append((model_name, benchmark, score, (row.get(date_col) or "").strip() if date_col else None))

    if not rows:
        index.sources_loaded.append("epoch_ai")
        index.warnings.append(
            f"Epoch AI CSV at {path} held no code-generation benchmark rows."
        )
        return

    # Epoch reports accuracies as fractions; a file that ranges above 1 is
    # on a 0-100 scale instead. Decide once per file rather than per row.
    scale = "0-1" if max(row[2] for row in rows) <= 1.0 else "0-100"

    for model_name, benchmark, score, date in rows:
        index.add(
            match_key(model_name),
            ExternalScore(
                source="epoch_ai",
                benchmark_name=benchmark,
                score=score,
                score_scale=scale,
                reported_date=date or None,
                matched_name=model_name,
                notes="Epoch AI, 'Capabilities & Benchmarking'. epoch.ai (2026). CC-BY.",
            ),
        )
    index.sources_loaded.append("epoch_ai")


# --- Public entry point ----------------------------------------------


def build_external_index(
    aa_path: Path = AA_CACHE_PATH, epoch_path: Path = EPOCH_CSV_PATH
) -> ExternalScoreIndex:
    """
    Load every available external source once and return a lookup index.
    Call this once per scoring run, not once per model.
    """
    index = ExternalScoreIndex()
    load_artificial_analysis(index, aa_path)
    load_epoch_ai(index, epoch_path)
    return index


if __name__ == "__main__":
    print("Fetching the Artificial Analysis catalog...")
    catalog = fetch_artificial_analysis_catalog()
    save_artificial_analysis_cache(catalog)
    print(f"Saved {len(catalog)} models to {AA_CACHE_PATH}")

    index = build_external_index()
    print(f"Sources loaded: {index.sources_loaded or 'none'}")
    print(f"Models with external scores: {len(index.by_key)}")
    for warning in index.warnings:
        print(f"  warning: {warning}")
