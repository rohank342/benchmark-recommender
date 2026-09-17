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
| [`enrich_scores.py`](enrich_scores.py) | Loads external benchmark catalogs (Artificial Analysis API, Epoch AI CSV) in bulk and indexes them for lookup. |
| [`model_matching.py`](model_matching.py) | Reduces Hub repo ids and external sources' model labels to a common match key. |
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

# 2. (optional) pull external benchmark scores — see "External sources" below
export ARTIFICIAL_ANALYSIS_API_KEY=...
python enrich_scores.py

# 3. launch the app — falls back to built-in mock models if step 1 was skipped
python app.py
```

Run the tests with `pytest`.

## External sources

Both sources are optional; whatever is missing is reported as a warning at
startup and the trust score accounts for the reduced source coverage.

**Artificial Analysis** — create a key at
<https://artificialanalysis.ai/data-api> and export it as
`ARTIFICIAL_ANALYSIS_API_KEY`, then run `python enrich_scores.py` to cache
the catalog to `data/artificial_analysis.json` (gitignored). The free tier
allows 100 requests per 24h and returns headline indices only; a paid key
also returns `huggingface_url` (exact repo matching instead of name
matching) and the code-specific `artificial_analysis_coding_index`.

**Epoch AI** — no public API. Download the benchmark CSV from
<https://epoch.ai/benchmarks/use-this-data#download-this-data> and save it
as `data/epoch_benchmarks.csv`. Only code-relevant benchmarks are used.
Their data is CC-BY: credit "Epoch AI, 'Capabilities & Benchmarking'.
epoch.ai (2026)" wherever you display it.

## Where to plug in real logic later

Search the codebase for `TODO(you)` — every stub and rule-of-thumb constant
is marked. Highlights:

- **`scoring.py`** — trust-discount tuning knobs (`SOURCE_COUNT_WEIGHTS`,
  `STALENESS_HALF_LIFE_DAYS`, `SELF_REPORT_PENALTY`) are reasonable
  starting guesses, not calibrated numbers.
- **`enrich_scores.py`** — Epoch's CSV column names are detected from a list
  of plausible spellings (`_EPOCH_*_COLUMNS`), since they aren't a published
  contract. Unrecognized headers are reported at startup.
- **`model_matching.py`** — matching is exact-on-normalized-key only. Loosening
  it would raise coverage at the risk of attributing one model's scores to
  another.
- **`hardware_filter.py`** — VRAM-per-billion-params multipliers are rule-of-
  thumb, not measured; also doesn't yet account for context length / KV-cache
  growth.
