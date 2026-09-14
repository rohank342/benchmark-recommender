# OpenModel Recommender (v1)

Recommends the best open-weight Hugging Face **code generation** model for a
given GPU VRAM budget, combining benchmark scores with a "trust score" that
discounts scores backed by few independent sources or that are stale
(inspired by Epoch AI's benchmark-reliability flagging).

## Scope (v1)

- Task type: code generation only.
- Filter: GPU VRAM budget only.

## Project layout

| File | Purpose |
|---|---|
| [`fetch_models.py`](fetch_models.py) | Pulls code-gen models from the HF Hub, caches to `data/models_raw.json`. |
| [`enrich_scores.py`](enrich_scores.py) | Stubbed external benchmark lookups (Artificial Analysis, Epoch AI) — **mock data today**, real API keys TODO. |
| [`scoring.py`](scoring.py) | Normalizes benchmark numbers, applies the trust discount, outputs a composite score. |
| [`hardware_filter.py`](hardware_filter.py) | Estimates fp16/8-bit/4-bit VRAM needs from param count and filters by budget. |
| [`app.py`](app.py) | Gradio UI tying it all together. |

## Setup

```bash
pip install -r requirements.txt
```

or with `uv`:

```bash
uv venv
uv pip install -r requirements.txt
```

## Run

```bash
# 1. (optional but recommended) pull real model data from the Hub
python fetch_models.py

# 2. launch the app — falls back to built-in mock models if step 1 was skipped
python app.py
```

## Where to plug in real logic later

Search the codebase for `TODO(you)` — every stub and rule-of-thumb constant
is marked. Highlights:

- **`enrich_scores.py`** — `fetch_external_score()` returns mock data from
  both `_fetch_from_artificial_analysis` and `_fetch_from_epoch_ai`. Set
  `ARTIFICIAL_ANALYSIS_API_KEY` / `EPOCH_AI_API_KEY` env vars and replace
  those two function bodies with real HTTP calls.
- **`scoring.py`** — trust-discount tuning knobs (`SOURCE_COUNT_WEIGHTS`,
  `STALENESS_HALF_LIFE_DAYS`, `CONTAMINATION_PENALTY`) are reasonable
  starting guesses, not calibrated numbers.
- **`hardware_filter.py`** — VRAM-per-billion-params multipliers are rule-of-
  thumb, not measured; also doesn't yet account for context length / KV-cache
  growth.
