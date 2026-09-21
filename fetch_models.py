"""
fetch_models.py
================
Pulls candidate code-generation models from the Hugging Face Hub and
extracts the raw fields the rest of the pipeline needs:

    model_id, params_billion, license, eval_results, downloads,
    last_modified

Run standalone to (re)build the local cache:

    python fetch_models.py

This writes data/models_raw.json, which enrich_scores.py / scoring.py /
app.py all read so we don't hammer the Hub API on every Gradio interaction.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from huggingface_hub import HfApi

DATA_DIR = Path(__file__).parent / "data"
RAW_CACHE_PATH = DATA_DIR / "models_raw.json"

# Tags/keywords used to narrow the Hub search to code-generation models.
# v1 scope is code-gen only, per project spec.
CODE_GEN_TAGS = ["code", "code-generation", "coding"]
CODE_KEYWORDS = ["code", "coder", "codegen", "coding"]

# How many models to pull per tag search. Keep modest for a fast demo;
# raise once you want broader coverage.
MODELS_PER_QUERY = 50

# Properties to request from the Hub. `full=True` does NOT include card
# metadata or safetensors param counts, so ask for them explicitly.
# (`expand` can't be combined with `full` / `cardData`.)
EXPAND_PROPERTIES = [
    "cardData",
    "safetensors",
    "downloads",
    "likes",
    "lastModified",
    "tags",
    "pipeline_tag",
]


@dataclass
class RawModel:
    model_id: str
    params_billion: Optional[float]
    license: Optional[str]
    eval_results: list[dict[str, Any]] = field(default_factory=list)
    downloads: int = 0
    likes: int = 0
    last_modified: Optional[str] = None
    tags: list[str] = field(default_factory=list)
    pipeline_tag: Optional[str] = None


def _estimate_params_from_id(model_id: str) -> Optional[float]:
    """
    Fallback heuristic: many model repo names embed the parameter count,
    e.g. "deepseek-coder-6.7b-instruct" or "CodeLlama-13b-hf".
    Returns billions of params as a float, or None if no match.
    """
    match = re.search(r"(\d+(?:\.\d+)?)\s*[bB](?:illion)?(?:[-_]|$)", model_id)
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            return None
    return None


def _extract_params_billion(model_info) -> Optional[float]:
    """
    Prefer the exact parameter count the Hub computes from safetensors
    metadata (model_info.safetensors.total) when available; otherwise
    fall back to parsing the repo name.
    """
    safetensors = getattr(model_info, "safetensors", None)
    if safetensors is not None:
        total = getattr(safetensors, "total", None)
        if total:
            return round(total / 1e9, 2)
    return _estimate_params_from_id(model_info.id)


def _extract_license(card_dict: dict[str, Any], tags: list[str]) -> Optional[str]:
    """Card metadata license, falling back to the Hub's `license:<id>` tag."""
    license_value = card_dict.get("license")
    if isinstance(license_value, list):
        license_value = license_value[0] if license_value else None
    if license_value:
        return str(license_value)
    for tag in tags:
        if tag.startswith("license:"):
            return tag.split(":", 1)[1]
    return None


def _extract_eval_results(card_data: dict[str, Any] | None) -> list[dict[str, Any]]:
    """
    The Hub's model card metadata can carry a standard `model-index` /
    `eval_results` block (the same schema used to render the "Results"
    widget on a model page). Pull whatever is there as-is; scoring.py
    is responsible for normalizing/interpreting it later.
    """
    if not card_data:
        return []
    results: list[dict[str, Any]] = []
    model_index = card_data.get("model-index") or card_data.get("model_index")
    if not model_index:
        return results
    # Card metadata is user-written YAML, so any level may be missing/null
    # or the wrong type — skip anything that isn't shaped as expected.
    if not isinstance(model_index, list):
        return results
    for entry in model_index:
        if not isinstance(entry, dict):
            continue
        for result_group in entry.get("results") or []:
            if not isinstance(result_group, dict):
                continue
            metrics = result_group.get("metrics") or []
            dataset = result_group.get("dataset") or {}
            task = result_group.get("task") or {}
            for metric in metrics:
                if not isinstance(metric, dict):
                    continue
                results.append(
                    {
                        "task": task.get("type") if isinstance(task, dict) else None,
                        "dataset": dataset.get("name"),
                        "metric_name": metric.get("type"),
                        "metric_value": metric.get("value"),
                    }
                )
    return results


def fetch_code_gen_models(limit_per_query: int = MODELS_PER_QUERY) -> list[RawModel]:
    """
    Query the Hub for text-generation models tagged/named for code, dedupe,
    and return a list of RawModel records.
    """
    api = HfApi()
    seen: dict[str, RawModel] = {}

    for tag in CODE_GEN_TAGS:
        models = api.list_models(
            pipeline_tag="text-generation",
            tags=[tag],
            sort="downloads",
            direction=-1,
            limit=limit_per_query,
            expand=EXPAND_PROPERTIES,
        )
        for m in models:
            if m.id in seen:
                continue
            card_data = getattr(m, "card_data", None)
            card_dict = card_data.to_dict() if hasattr(card_data, "to_dict") else (card_data or {})
            if not isinstance(card_dict, dict):
                card_dict = {}
            tags = list(getattr(m, "tags", []) or [])
            last_modified = getattr(m, "last_modified", None)

            seen[m.id] = RawModel(
                model_id=m.id,
                params_billion=_extract_params_billion(m),
                license=_extract_license(card_dict, tags),
                eval_results=_extract_eval_results(card_dict),
                downloads=getattr(m, "downloads", 0) or 0,
                likes=getattr(m, "likes", 0) or 0,
                last_modified=last_modified.isoformat() if last_modified else None,
                tags=tags,
                pipeline_tag=getattr(m, "pipeline_tag", None),
            )

    return list(seen.values())


def save_raw_cache(models: list[RawModel], path: Path = RAW_CACHE_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "models": [asdict(m) for m in models],
    }
    path.write_text(json.dumps(payload, indent=2))


def load_raw_cache(path: Path = RAW_CACHE_PATH) -> dict[str, Any]:
    if not path.exists():
        return {"fetched_at": None, "models": []}
    return json.loads(path.read_text())


if __name__ == "__main__":
    print("Fetching code-generation models from the Hugging Face Hub...")
    models = fetch_code_gen_models()
    print(f"Found {len(models)} unique models.")
    save_raw_cache(models)
    print(f"Saved to {RAW_CACHE_PATH}")
