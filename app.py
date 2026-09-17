"""
app.py
======
Gradio front-end for OpenModel Recommender (v1: code generation only).

User picks a task type (only "code generation" exists for now — the
dropdown is there so adding more tasks later is a small diff, not a
rewrite) and an available GPU VRAM budget, and gets back a ranked table
of models that fit, sorted by composite score.

Run with:

    python app.py

On first run, if data/models_raw.json doesn't exist yet, this will
fall back to a small built-in MOCK_MODELS list (clearly marked below)
so the demo still works without hitting the network. Run
`python fetch_models.py` first to populate real data from the Hub.
"""

from __future__ import annotations

from dataclasses import asdict
from functools import lru_cache
from typing import Any

import gradio as gr
import pandas as pd

from enrich_scores import build_external_index
from fetch_models import RAW_CACHE_PATH, load_raw_cache
from hardware_filter import filter_models_by_vram
from scoring import score_models

# --- Fallback data so the demo runs even with an empty/missing cache ---
# TODO(you): remove once `python fetch_models.py` is part of your normal
# setup flow, or keep as an offline-demo fallback — your call.
MOCK_MODELS: list[dict[str, Any]] = [
    {
        "model_id": "example-org/mock-coder-7b",
        "params_billion": 7.0,
        "license": "apache-2.0",
        "eval_results": [{"metric_name": "pass@1", "metric_value": 48.5}],
        "downloads": 50000,
        "last_modified": "2025-05-01",
    },
    {
        "model_id": "example-org/mock-coder-13b",
        "params_billion": 13.0,
        "license": "llama2",
        "eval_results": [{"metric_name": "pass@1", "metric_value": 55.0}],
        "downloads": 30000,
        "last_modified": "2024-11-15",
    },
    {
        "model_id": "example-org/mock-coder-34b",
        "params_billion": 34.0,
        "license": "apache-2.0",
        "eval_results": [{"metric_name": "pass@1", "metric_value": 62.3}],
        "downloads": 15000,
        "last_modified": "2025-02-20",
    },
    {
        "model_id": "example-org/mock-coder-1.3b",
        "params_billion": 1.3,
        "license": "mit",
        "eval_results": [{"metric_name": "pass@1", "metric_value": 32.0}],
        "downloads": 80000,
        "last_modified": "2025-07-10",
    },
]

TASK_TYPES = ["code generation"]  # TODO(you): extend once v1 scope widens beyond code-gen


def _load_models() -> list[dict[str, Any]]:
    cache = load_raw_cache(RAW_CACHE_PATH)
    models = cache.get("models") or []
    if models:
        return models
    print(
        f"[app.py] No cached models found at {RAW_CACHE_PATH}. "
        "Using built-in MOCK_MODELS. Run `python fetch_models.py` for real data."
    )
    return MOCK_MODELS


@lru_cache(maxsize=1)
def _external_index():
    """
    Load external sources once per process. They're bulk catalogs read
    from disk, so rebuilding them on every click would be wasted work.
    Restart the app (or clear this cache) after refreshing them.
    """
    index = build_external_index()
    print(f"[app.py] External sources loaded: {index.sources_loaded or 'none'}")
    for warning in index.warnings:
        print(f"[app.py] warning: {warning}")
    return index


def recommend(task_type: str, vram_gb: float) -> pd.DataFrame:
    if task_type != "code generation":
        # v1 scope guard — should be unreachable given the dropdown, but
        # fail loudly rather than silently returning code-gen results.
        return pd.DataFrame([{"error": f"Task type '{task_type}' not supported in v1."}])

    raw_models = _load_models()
    scored = score_models(raw_models, index=_external_index())

    scored_dicts = [asdict(s) for s in scored]
    fitted = filter_models_by_vram(scored_dicts, available_vram_gb=vram_gb)

    if not fitted:
        return pd.DataFrame(
            [{"message": f"No models fit within {vram_gb} GB VRAM at any quantization level."}]
        )

    rows = []
    for m in fitted:
        rows.append(
            {
                "model_id": m["model_id"],
                "composite_score": m["composite_score"],
                "trust_score": m["trust_score"],
                "raw_benchmark_score": m["raw_benchmark_score"],
                "params_B": m["params_billion"],
                "license": m["license"],
                "best_fit_quant": m["best_fit_quant"],
                "vram_fp16_gb": m["vram_fp16_gb"],
                "vram_8bit_gb": m["vram_8bit_gb"],
                "vram_4bit_gb": m["vram_4bit_gb"],
                "num_sources": m["num_sources"],
                "sources": ", ".join(m["sources"]) or "—",
                "self_reported_only": m["self_reported_only"],
                "downloads": m["downloads"],
            }
        )

    df = pd.DataFrame(rows)
    df = df.sort_values(by="composite_score", ascending=False, na_position="last")
    return df.reset_index(drop=True)


def build_interface() -> gr.Blocks:
    with gr.Blocks(title="OpenModel Recommender") as demo:
        gr.Markdown(
            "# OpenModel Recommender (v1: code generation)\n"
            "Recommends open-weight Hugging Face code-generation models "
            "for your task and GPU VRAM budget, combining benchmark "
            "scores with a trust discount for source coverage + staleness.\n\n"
            "`trust_score` discounts models whose numbers come from few "
            "independent sources, are stale, or are only self-reported on "
            "the model's own card. External sources load from local caches "
            "— see `enrich_scores.py` for how to refresh them."
        )
        with gr.Row():
            task_dropdown = gr.Dropdown(
                choices=TASK_TYPES, value=TASK_TYPES[0], label="Task type"
            )
            vram_input = gr.Number(value=8, label="Available GPU VRAM (GB)", precision=1)
        submit_btn = gr.Button("Recommend models", variant="primary")
        output_table = gr.Dataframe(label="Ranked recommendations", wrap=True)

        submit_btn.click(fn=recommend, inputs=[task_dropdown, vram_input], outputs=output_table)
        demo.load(fn=recommend, inputs=[task_dropdown, vram_input], outputs=output_table)

    return demo


if __name__ == "__main__":
    interface = build_interface()
    interface.launch()
