"""
app.py
======
Gradio front-end, in two tabs that reflect the order the questions
should be asked in:

  "Which benchmark should I trust?"  — the primary question. Describe a
      task, see the benchmarks for it ranked by trust, with the factor
      that limits each one. Popularity is not a column here.

  "Which model should I use?"        — downstream. The same hardware
      filtering as before, but model scores are weighted by benchmark
      trust, and each row shows which benchmarks produced its score.

Run with:

    python app.py

The benchmark tab works offline from the catalog in fetch_benchmarks.py
and the score data in data/. The model tab needs data/models_raw.json —
run `python fetch_models.py` first, or it says so rather than inventing
placeholder models.
"""

from __future__ import annotations

from dataclasses import asdict
from functools import lru_cache
from typing import Any

import gradio as gr
import pandas as pd

from benchmark_scoring import score_all_benchmarks, trust_by_key
from device_profiles import DEVICES, detect_local_device, get_device, usable_memory_gb
from enrich_scores import build_external_index
from fetch_models import RAW_CACHE_PATH, load_raw_cache
from hardware_filter import filter_models_by_vram
from scoring import score_models
from task_matcher import CATEGORY_KEYWORDS, all_categories, recommend_benchmarks

# Task categories now come from the benchmark catalog rather than a
# hardcoded single option.
TASK_TYPES = list(all_categories())


def _load_models() -> list[dict[str, Any]]:
    """
    The cached Hub models, or an empty list.

    There is deliberately no built-in fallback. Four fake models made a
    missing fetch look like a working app with odd results, which is a
    worse failure than an empty table saying what to run.
    """
    models = load_raw_cache(RAW_CACHE_PATH).get("models") or []
    if not models:
        print(
            f"[app.py] No model cache at {RAW_CACHE_PATH} — "
            "run `python fetch_models.py`. The benchmark tab works without it."
        )
    return models


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


@lru_cache(maxsize=1)
def _benchmark_trust():
    """
    Score every benchmark once per process. Trust is a property of the
    benchmark, not of any query, and the underlying data is local.
    """
    return score_all_benchmarks()


def rank_benchmarks(task_description: str) -> tuple[str, pd.DataFrame]:
    """
    The primary view: which benchmarks are worth believing for this task.

    Returns (what the matcher concluded, ranked table). Deliberately
    reports no popularity column — the whole point is that a benchmark's
    fame and its current validity have come apart.
    """
    scored = _benchmark_trust()
    match, benchmarks = recommend_benchmarks(task_description or "", scored)

    if not benchmarks:
        return (
            f"{match.explanation}\n\nNo benchmarks catalogued for that category yet.",
            pd.DataFrame(),
        )

    rows = []
    for trust in benchmarks:
        benchmark = trust.benchmark
        from fetch_benchmarks import describe_population

        saturation = (
            f"{trust.measured_saturation * 100:.0f}% (measured, n={trust.models_measured})"
            if trust.measured_saturation is not None
            else "unknown (no score data)"
        )
        # Saturation depends on which models you measure over, so name the
        # population rather than implying one universal number.
        measured_over = (
            describe_population(trust.primary_source) if trust.primary_source else "—"
        )
        by_source = (
            " | ".join(
                f"{describe_population(src)}: {value * 100:.0f}% (n={n})"
                for src, (value, n) in trust.saturation_by_source.items()
            )
            or "—"
        )
        factors = {f.name: f for f in trust.factors}
        rows.append(
            {
                "benchmark": benchmark.name,
                "trust_score": trust.trust_score,
                "category": benchmark.category,
                "saturation": saturation,
                "measured_over": measured_over,
                "saturation_by_source": by_source,
                "limiting_factor": trust.dominant_factor.name if trust.dominant_factor else "—",
                "why": trust.summary,
                "released": benchmark.release_date or "unknown",
                "discrimination": round(factors["discrimination"].value, 2),
                "freshness": round(factors["freshness"].value, 2),
                "reproducibility": round(factors["reproducibility"].value, 2),
                "specificity": round(factors["specificity"].value, 2),
                "evidence": factors["discrimination"].basis,
                "flags": ", ".join(trust.penalties) or "—",
            }
        )

    header = match.explanation
    top = benchmarks[0]
    header += (
        f"\n\n**Most trustworthy for this task: {top.benchmark.name}** "
        f"({top.trust_score:.1f}/100). {top.summary}"
    )
    # Name-and-shame the popular-but-weak, since that's the point of the tool.
    weak = [t for t in benchmarks if t.trust_score < 35]
    if weak:
        header += (
            "\n\n⚠️ Low-trust benchmarks in this category, often still quoted: "
            + ", ".join(f"{t.benchmark.name} ({t.trust_score:.0f})" for t in weak)
        )
    return header, pd.DataFrame(rows)


def recommend(
    task_type: str,
    vram_gb: float,
    context_tokens: float = 8192,
    device_key: str = None,
) -> pd.DataFrame:
    context = int(context_tokens or 8192)
    device = get_device(device_key)
    # On unified memory the OS keeps a share; on a discrete card, only a
    # sliver goes to the driver. Either way the model gets less than the
    # number on the box.
    budget = usable_memory_gb(device, vram_gb)
    raw_models = _load_models()
    if not raw_models:
        return pd.DataFrame(
            [
                {
                    "message": "No model data. Run `python fetch_models.py` to "
                    "populate data/models_raw.json, then restart the app."
                }
            ]
        )
    scored = score_models(raw_models, index=_external_index())

    scored_dicts = [asdict(s) for s in scored]
    # Carry through the fields scoring doesn't model but memory needs.
    by_id = {m["model_id"]: m for m in raw_models}
    for model in scored_dicts:
        model["architecture"] = by_id.get(model["model_id"], {}).get("architecture", {})
        model["tags"] = by_id.get(model["model_id"], {}).get("tags", [])

    fitted = filter_models_by_vram(
        scored_dicts, available_vram_gb=budget, context_tokens=context, device=device
    )

    if not fitted:
        return pd.DataFrame(
            [
                {
                    "message": f"Nothing {device.label} can run fits in {budget} GB "
                    f"usable (of {vram_gb} stated) at {context:,} tokens of context."
                }
            ]
        )

    rows = []
    for m in fitted:
        max_context = m["max_context"]
        breakdown = m.get("benchmark_breakdown") or []
        rows.append(
            {
                "model_id": m["model_id"],
                "composite_score": m["composite_score"],
                # Which benchmarks produced this score, strongest trust first.
                "scored_on": " | ".join(
                    f"{b['benchmark']} ({b['trust']:.0f} trust → {b['score']:.2f})"
                    for b in breakdown[:3]
                )
                or "—",
                "trust_score": m["trust_score"],
                "params_B": m["params_billion"],
                "license": m["license"],
                "precision": m["best_fit_quant"] or "—",
                "vram_total_gb": m["vram_total_gb"],
                "weights_gb": m["vram_weights_gb"],
                "kv_cache_gb": m["vram_kv_cache_gb"],
                "kv_estimated": m["kv_cache_estimated"],
                "runtime": m["runtime_format"],
                "ships_as": f"{m['native_quant']}-bit" if m["native_quant"] else "full precision",
                "context_ok": None if max_context is None else context <= max_context,
                "max_context": max_context,
                "sources": ", ".join(m["sources"]) or "—",
                "corroborated": m["composite_score"] is not None
                and not m["self_reported_only"],
                "provenance_verified": m["provenance_verified"],
                "size_known": m["size_known"],
                "downloads": m["downloads"],
            }
        )

    df = pd.DataFrame(rows)
    # Same tiering as scoring.rank_key: models whose size is known first
    # (an unknown-size row can't be said to fit), then confirmed
    # provenance, then corroborated, then self-reported, then unscored.
    df = df.sort_values(
        by=["size_known", "provenance_verified", "corroborated", "composite_score"],
        ascending=[False, False, False, False],
        na_position="last",
    )
    return df.reset_index(drop=True)


def build_interface() -> gr.Blocks:
    detected = detect_local_device()

    with gr.Blocks(title="Benchmark Recommender") as demo:
        gr.Markdown(
            "# Benchmark Recommender\n"
            "A benchmark's popularity is not evidence that it still works. "
            "Labs optimize against well-known benchmarks until the leaderboard "
            "stops separating models, and public test sets leak into training "
            "data. **Start by choosing a benchmark you can believe** — model "
            "rankings follow from that, not the other way round."
        )

        with gr.Tab("Which benchmark should I trust?"):
            gr.Markdown(
                "Describe your task in your own words. Benchmarks are ranked by "
                "trust — saturation measured from real score distributions where "
                "data exists, curated where it doesn't."
            )
            with gr.Row():
                task_input = gr.Textbox(
                    label="What are you actually doing?",
                    placeholder="e.g. fixing bugs in a large legacy repository",
                    value="code generation",
                    scale=3,
                )
                benchmark_btn = gr.Button("Rank benchmarks", variant="primary", scale=1)
            gr.Examples(
                examples=[
                    ["code generation"],
                    ["building an agent that runs shell commands"],
                    ["medical QA for clinicians"],
                    ["fixing bugs in a large legacy repository"],
                    ["checking whether answers are factually accurate"],
                ],
                inputs=task_input,
            )
            benchmark_summary = gr.Markdown()
            benchmark_table = gr.Dataframe(label="Benchmarks, ranked by trust", wrap=True)

            benchmark_btn.click(
                fn=rank_benchmarks,
                inputs=task_input,
                outputs=[benchmark_summary, benchmark_table],
            )
            demo.load(
                fn=rank_benchmarks,
                inputs=task_input,
                outputs=[benchmark_summary, benchmark_table],
            )

        with gr.Tab("Which model should I use?"):
            gr.Markdown(
                "Model scores are weighted by benchmark trust: a result on a "
                "saturated benchmark counts for less than one on a benchmark that "
                "still discriminates. The `scored_on` column shows which "
                "benchmarks produced each score.\n\n"
                "`trust_score` here is a separate thing — how much to believe the "
                "*report* (independent sources, staleness, self-reporting), not "
                "the benchmark itself."
            )
            with gr.Row():
                task_dropdown = gr.Dropdown(
                    choices=TASK_TYPES, value=TASK_TYPES[0], label="Task category"
                )
                device_dropdown = gr.Dropdown(
                    choices=[(profile.label, key) for key, profile in DEVICES.items()],
                    value=detected,
                    label="Your hardware",
                    info="Decides which formats are runnable at all — AWQ and FP8 "
                    "need CUDA, MLX needs Apple Silicon.",
                )
                vram_input = gr.Number(
                    value=8,
                    label="Memory (GB)",
                    precision=1,
                    info="VRAM on a discrete GPU; total unified memory on a Mac.",
                )
                context_input = gr.Dropdown(
                    choices=[
                        ("4K (short edits)", 4096),
                        ("8K", 8192),
                        ("32K (a file or two)", 32768),
                        ("128K (whole repo)", 131072),
                    ],
                    value=8192,
                    label="Context length",
                    info="The KV cache grows with context — at 128K it can exceed the weights.",
                )
            device_note = gr.Markdown(f"*{DEVICES[detected].note}*")
            submit_btn = gr.Button("Recommend models", variant="primary")
            output_table = gr.Dataframe(label="Ranked recommendations", wrap=True)

            device_dropdown.change(
                fn=lambda key: f"*{DEVICES[key].note}*",
                inputs=device_dropdown,
                outputs=device_note,
            )
            model_inputs = [task_dropdown, vram_input, context_input, device_dropdown]
            submit_btn.click(fn=recommend, inputs=model_inputs, outputs=output_table)
            demo.load(fn=recommend, inputs=model_inputs, outputs=output_table)

    return demo


if __name__ == "__main__":
    interface = build_interface()
    interface.launch()
