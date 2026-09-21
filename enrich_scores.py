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

  Epoch AI — download the benchmark export from
  https://epoch.ai/benchmarks/use-this-data#download-this-data and unzip it
  to data/epoch_benchmarks/. Their data is CC-BY: credit
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
EPOCH_DATA_DIR = DATA_DIR / "epoch_benchmarks"

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

# Epoch's export is a directory: benchmark_metadata.csv indexes ~86
# benchmarks, each with its own CSV, score column, and scale factor.
EPOCH_METADATA_FILE = "benchmark_metadata.csv"

# Epoch covers maths, games, agentic work and more; v1 scope is code
# generation. These are the code-relevant benchmarks in their export, by
# the exact names used in benchmark_metadata.csv.
EPOCH_CODE_BENCHMARKS = frozenset(
    {
        "SWE-Bench verified",
        "SWE-bench Pro",
        "MirrorCode",
        "Aider polyglot",
        "DeepSWE",
        "FrontierCode",
        "FrontierSWE",
        "GSO-Bench",
        "Terminal Bench",
        "CursorBench",
        "AlgoTune",
        "ALE-Bench",
        "SciCode",
        "WebDev Arena",
    }
)

# Per-benchmark CSVs name the model in "Model version" and carry the
# evaluation date; the score column varies and is named in the metadata.
_EPOCH_MODEL_COLUMNS = ("model_version", "model", "model_name")
_EPOCH_DATE_COLUMNS = ("date_of_evaluation", "release_date", "date")


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


def _load_epoch_benchmark_file(
    index: ExternalScoreIndex, directory: Path, meta: dict[str, str]
) -> int:
    """Index one benchmark's CSV, described by its metadata row."""
    source_file = (meta.get("source_file") or "").strip()
    score_column = (meta.get("score_column") or "").strip()
    benchmark = (meta.get("benchmark") or "").strip()
    path = directory / source_file
    if not source_file or not score_column or not path.exists():
        return 0

    # `scale` is the multiplier that converts the column to a 0-1
    # fraction: 1.0 where scores are already fractions, 0.01 where the
    # column is a percentage.
    try:
        scale_factor = float(meta.get("scale") or 1.0)
    except ValueError:
        scale_factor = 1.0

    added = 0
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        fieldnames = reader.fieldnames or []
        model_col = _pick_column(fieldnames, _EPOCH_MODEL_COLUMNS)
        date_col = _pick_column(fieldnames, _EPOCH_DATE_COLUMNS)
        if not model_col or score_column not in fieldnames:
            index.warnings.append(
                f"Epoch file {source_file} lacks a model or '{score_column}' column."
            )
            return 0

        for row in reader:
            model_name = (row.get(model_col) or "").strip()
            raw = (row.get(score_column) or "").strip().rstrip("%")
            if not model_name or not raw:
                continue
            try:
                score = float(raw) * scale_factor
            except ValueError:
                continue
            index.add(
                match_key(model_name),
                ExternalScore(
                    source="epoch_ai",
                    benchmark_name=benchmark,
                    score=score,
                    score_scale="0-1",  # normalized by the metadata's scale factor
                    reported_date=(row.get(date_col) or "").strip() or None,
                    matched_name=model_name,
                    notes="Epoch AI, 'Capabilities & Benchmarking'. epoch.ai (2026). CC-BY.",
                ),
            )
            added += 1
    return added


def load_epoch_ai(index: ExternalScoreIndex, path: Path = EPOCH_DATA_DIR) -> None:
    """
    Add scores from a downloaded Epoch AI benchmark export to `index`.

    The export is a directory: `benchmark_metadata.csv` lists every
    benchmark with its source file, score column and scale factor, and
    each benchmark has its own CSV. Only the code-generation benchmarks
    in EPOCH_CODE_BENCHMARKS are loaded.
    """
    metadata_path = path / EPOCH_METADATA_FILE
    if not metadata_path.exists():
        index.warnings.append(
            f"No Epoch AI export at {path} (expected {EPOCH_METADATA_FILE} inside) — "
            "download it from https://epoch.ai/benchmarks/use-this-data#download-this-data"
        )
        return

    with metadata_path.open(newline="", encoding="utf-8") as handle:
        metadata = [
            row
            for row in csv.DictReader(handle)
            if (row.get("benchmark") or "").strip() in EPOCH_CODE_BENCHMARKS
        ]

    added = sum(_load_epoch_benchmark_file(index, path, row) for row in metadata)
    index.sources_loaded.append("epoch_ai")
    if not added:
        index.warnings.append(
            f"Epoch AI export at {path} held no usable code-benchmark scores."
        )


def epoch_catalog_targets(path: Path = EPOCH_DATA_DIR) -> list[tuple[str, str, Optional[str]]]:
    """
    Models Epoch has a code-benchmark score for, as
    (match key, label, crediting organization) — the same shape
    fetch_models.fetch_models_for_catalog() consumes.
    """
    metadata_path = path / EPOCH_METADATA_FILE
    if not metadata_path.exists():
        return []

    with metadata_path.open(newline="", encoding="utf-8") as handle:
        files = [
            (row.get("source_file") or "").strip()
            for row in csv.DictReader(handle)
            if (row.get("benchmark") or "").strip() in EPOCH_CODE_BENCHMARKS
        ]

    targets: dict[str, tuple[str, str, Optional[str]]] = {}
    for source_file in files:
        file_path = path / source_file
        if not source_file or not file_path.exists():
            continue
        with file_path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            model_col = _pick_column(reader.fieldnames or [], _EPOCH_MODEL_COLUMNS)
            org_col = _pick_column(reader.fieldnames or [], ("organization", "creator"))
            if not model_col:
                continue
            for row in reader:
                label = (row.get(model_col) or "").strip()
                key = match_key(label)
                if key:
                    targets.setdefault(
                        key, (key, label, (row.get(org_col) or "").strip() or None if org_col else None)
                    )
    return list(targets.values())


# --- Public entry point ----------------------------------------------


def build_external_index(
    aa_path: Path = AA_CACHE_PATH, epoch_path: Path = EPOCH_DATA_DIR
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
