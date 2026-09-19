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
from typing import Any, Iterable, Optional

from huggingface_hub import HfApi
from huggingface_hub.utils import HfHubHTTPError

from model_matching import identity_string, match_key

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
    # False when this repo was located by matching an external source's
    # model *name* and no repo from the crediting organization matched —
    # i.e. we can't confirm it hosts the weights that were benchmarked.
    provenance_verified: bool = True


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


def _to_raw_model(model_info, provenance_verified: bool = True) -> RawModel:
    """Build a RawModel from one Hub ModelInfo."""
    card_data = getattr(model_info, "card_data", None)
    card_dict = card_data.to_dict() if hasattr(card_data, "to_dict") else (card_data or {})
    if not isinstance(card_dict, dict):
        card_dict = {}
    tags = list(getattr(model_info, "tags", []) or [])
    last_modified = getattr(model_info, "last_modified", None)

    return RawModel(
        model_id=model_info.id,
        params_billion=_extract_params_billion(model_info),
        license=_extract_license(card_dict, tags),
        eval_results=_extract_eval_results(card_dict),
        downloads=getattr(model_info, "downloads", 0) or 0,
        likes=getattr(model_info, "likes", 0) or 0,
        last_modified=last_modified.isoformat() if last_modified else None,
        tags=tags,
        pipeline_tag=getattr(model_info, "pipeline_tag", None),
        provenance_verified=provenance_verified,
    )


# Pipeline tags for repos that generate text. Multimodal chat models are
# tagged image-text-to-text but still write code, and excluding them sent
# e.g. Kimi K2.6 to a community requantization instead of moonshotai's repo.
WEIGHT_BEARING_PIPELINE_TAGS = {"text-generation", "image-text-to-text"}


def _has_real_weights(model_info) -> bool:
    """
    Guard against matching a model *name* to a repo that isn't that model's
    weights — e.g. searching "GPT-3.5 Turbo" surfaces `Xenova/gpt-3.5-turbo`,
    a tokenizer-only repo. Require a text-generating repo carrying weights.
    """
    total = getattr(getattr(model_info, "safetensors", None), "total", None)
    return (
        bool(total)
        and getattr(model_info, "pipeline_tag", None) in WEIGHT_BEARING_PIPELINE_TAGS
    )


# Words carrying no identity in an organization name, dropped before
# taking initials: "Institute of Foundation Models" -> "ifm".
_ORG_STOPWORDS = frozenset({"of", "the", "and", "for", "inc", "ltd", "llc", "labs", "lab"})

# Adoption that vouches for a repo when its owner can't be tied to the
# crediting organization by name. Publishers often use a brand or parent
# name that doesn't match their Hub org ("Kimi" vs `moonshotai`,
# "Alibaba" vs `Qwen`), so naming alone flags too many genuine repos.
# Either signal suffices: a widely-pulled repo and a widely-liked one are
# both hard to fake, and the repos that fail both are the ones worth
# doubting (339 downloads / 2 likes for `testaccount-ai/Qwen3.8-Max`).
MIN_DOWNLOADS_FOR_PROVENANCE = 5_000
MIN_LIKES_FOR_PROVENANCE = 100


def _owner_matches_creator(repo_id: str, creator: Optional[str]) -> bool:
    """
    Does the repo's owning org look like the organization the benchmark
    source credits, by full name or by initials? `Qwen/Qwen3-Coder` from
    creator "Qwen" matches directly; `IFM/K2-Horizon-7B` from "Institute
    of Foundation Models" matches on initials.
    """
    if not creator:
        return False
    owner = identity_string(repo_id.split("/", 1)[0]) or ""
    creator_key = identity_string(creator) or ""
    if not owner or not creator_key:
        return False
    if owner in creator_key or creator_key in owner:
        return True

    words = [w for w in re.split(r"[^A-Za-z0-9]+", creator) if w and w.lower() not in _ORG_STOPWORDS]
    initials = "".join(word[0].lower() for word in words)
    return len(initials) > 1 and (initials == owner or owner.startswith(initials))


def _provenance_verified(model_info, creator: Optional[str]) -> bool:
    """
    Can we believe this repo holds the weights the benchmark measured?

    Ideal evidence is the publisher's own org. Failing that, adoption
    stands in: a repo with real pull-through is the one the community
    treats as the model, whereas an impersonation has neither.
    """
    if _owner_matches_creator(model_info.id, creator):
        return True
    return (getattr(model_info, "downloads", 0) or 0) >= MIN_DOWNLOADS_FOR_PROVENANCE or (
        getattr(model_info, "likes", 0) or 0
    ) >= MIN_LIKES_FOR_PROVENANCE


def fetch_models_for_catalog(
    targets: Iterable[tuple[str, str, Optional[str]]], limit_per_search: int = 30
) -> list[RawModel]:
    """
    Resolve externally-benchmarked models to Hub repos. `targets` is an
    iterable of (match key, the source's label, crediting organization).

    Tag-based discovery alone surfaces whatever is popular on the Hub,
    which is mostly reuploads and fine-tunes that no benchmark org tracks.
    Starting from models that *have* independent scores and locating their
    weights is what gives the ranking anything to rank.

    Closed models (Gemini, Claude, GPT) don't resolve, which is the
    intended outcome — they aren't open-weight, so they aren't candidates.
    Among repos that do match, the publisher's own repo is preferred over
    community requantizations, and downloads break the remaining ties.
    """
    api = HfApi()
    found: dict[str, RawModel] = {}

    for key, label, creator in targets:
        try:
            candidates = [
                m
                for m in api.list_models(
                    search=label, limit=limit_per_search, expand=EXPAND_PROPERTIES
                )
                if match_key(m.id) == key and _has_real_weights(m)
            ]
        except HfHubHTTPError as exc:  # one bad search shouldn't end the run
            print(f"[fetch_models] search failed for {label!r}: {exc}")
            continue
        if not candidates:
            continue
        best = max(
            candidates,
            key=lambda m: (
                _owner_matches_creator(m.id, creator),
                getattr(m, "downloads", 0) or 0,
            ),
        )
        found[best.id] = _to_raw_model(
            best, provenance_verified=_provenance_verified(best, creator)
        )
    return list(found.values())


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
            seen[m.id] = _to_raw_model(m)

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
    from enrich_scores import artificial_analysis_catalog_targets, epoch_catalog_targets

    print("Fetching code-generation models from the Hugging Face Hub...")
    models = fetch_code_gen_models()
    print(f"  {len(models)} from tag search.")

    # Second pass: models an external source has actually benchmarked.
    # Tag search alone rarely surfaces them, and they're the only models
    # that end up with an independent score to rank on.
    targets = {t[0]: t for t in artificial_analysis_catalog_targets()}
    for target in epoch_catalog_targets():
        targets.setdefault(target[0], target)
    targets = list(targets.values())
    if targets:
        print(f"Resolving {len(targets)} externally-benchmarked models on the Hub...")
        by_id = {m.model_id: m for m in models}
        for model in fetch_models_for_catalog(targets):
            by_id.setdefault(model.model_id, model)
        models = list(by_id.values())
        print(f"  {len(models)} total after adding benchmarked models.")
    else:
        print("  No external catalog cached — run `python enrich_scores.py` first.")

    save_raw_cache(models)
    print(f"Saved {len(models)} models to {RAW_CACHE_PATH}")
