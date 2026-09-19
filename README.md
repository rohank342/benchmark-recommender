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
# 1. pull external benchmark scores first — see "External sources" below
export ARTIFICIAL_ANALYSIS_API_KEY=...
python enrich_scores.py

# 2. pull model data from the Hub
export HF_TOKEN=...        # recommended: anonymous access gets rate-limited
python fetch_models.py

# 3. launch the app — falls back to built-in mock models if step 2 was skipped
python app.py
```

Run `enrich_scores.py` *before* `fetch_models.py`: the fetch makes two
passes, one over code-tagged Hub models and one that locates the
externally-benchmarked models on the Hub. The second pass is what puts
models with independent scores into the candidate set, and it needs the
cached catalog. It makes one search per benchmarked model, so set
`HF_TOKEN` (any free Hub account) to avoid anonymous rate limits — a
rate-limited search is reported and skipped, not fatal.

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

**Epoch AI** — no public API. Their export is a zip of per-benchmark CSVs
indexed by `benchmark_metadata.csv`, downloaded from
<https://epoch.ai/benchmarks/use-this-data#download-this-data>. The
code-generation benchmarks from it are committed here under
`data/epoch_benchmarks/` (SWE-Bench verified, MirrorCode, Aider polyglot,
GSO-Bench, Terminal Bench, DeepSWE, FrontierCode) — to refresh, re-download
and copy those files over. Their data is CC-BY: credit "Epoch AI,
'Capabilities & Benchmarking'. epoch.ai (2026)" wherever you display it, as
`data/epoch_benchmarks/SOURCE.md` does.

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
- **`fetch_models.py`** — `MIN_DOWNLOADS_FOR_PROVENANCE` / `MIN_LIKES_FOR_PROVENANCE`
  decide when a repo is trusted to hold the weights a benchmark measured, for
  repos whose owner can't be tied to the crediting organization by name. They
  are judgement calls, picked by looking at the repos they separate.
- **`hardware_filter.py`** — VRAM-per-billion-params multipliers are rule-of-
  thumb, not measured; also doesn't yet account for context length / KV-cache
  growth.
