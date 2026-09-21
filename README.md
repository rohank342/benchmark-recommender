# Benchmark Recommender

**Which benchmark should you believe?** Popularity is not evidence that a
benchmark still works. Labs optimize against well-known benchmarks until the
leaderboard stops separating models, and public test sets leak into training
data — so HumanEval and MMLU keep getting quoted long after they stopped
discriminating. This scores *benchmarks* first. Model rankings are downstream:
a model's result is worth what the benchmark that produced it is worth.

The concrete case. For code generation, **HumanEval scores 28.7/100 and
MirrorCode scores 74.3.** HumanEval is the famous one. It is also 164 short
functions published in 2021, whose top ten models now span 7.9 points of the
usable range and average 92% of it — measured, from 125 models' scores — while
8–18% of its items appear in major pretraining corpora and the same models
score 39.4% lower on a decontaminated variant. MirrorCode is from 2026, holds
back ~34% of its tests so solutions can't be memorized, and its top ten still
spread out. Neither number is a matter of opinion about which benchmark is
fashionable.

---

## What you can and can't trust here

This matters more than the scores, so it comes first.

**Measured** — computed from real score distributions, reproducible from the
committed data:

| | coverage |
|---|---|
| Saturation (the `discrimination` factor) | 25 of 26 benchmarks |
| Cross-source agreement (`reproducibility`) | 6 of 26 |

**Curated** — read out of papers and reports by a human, cited in each entry's
`curation_notes` with a date:

| | coverage |
|---|---|
| Contamination rate (fraction of items in pretraining corpora) | 3 of 26 |
| Item error rate (wrong answer keys, broken tests) | 4 of 26 |
| Release dates, dataset sizes, holdout type | all 26 |

**Judgement calls** — defensible, argued in comments, but mine rather than
anybody's finding:

- `task_specificity` for all 26 benchmarks: how narrowly a benchmark maps to
  real work, 0–1.
- `independent_evaluators` for the 20 benchmarks where agreement can't be
  measured.
- Every weight and threshold: the 40/20/20/20 factor split, the two-year
  leakage half-life, the penalty curves.

The UI reports `measured` / `curated` / `unknown` per factor, per benchmark, so
you can see which kind of number you're looking at. If a number in the table
traces back to a guess, the guess is visible.

---

## Limitations

The ones that undercut the project, stated plainly:

**The weights are uncalibrated.** 40% discrimination, 20% each for freshness,
reproducibility and specificity, with a two-year leakage half-life. These are
judgement calls, and **[the backtest now partially fails](docs/BACKTEST.md)**.
Scored as of June 2024 against HF's retirement decision it gets 10 of 12 —
MMLU, which was retired, outranks MuSR, which was kept. The cause is MuSR's
hand-assigned specificity. Worse, sorting benchmarks by release date and
calling the newer half "kept" also scores 10 of 12, so on the only test
available the four weighted factors do not beat ranking by age. Weights that
would pass exist, but they disagree about which factor is wrong, so none were
applied.

**Saturation depends on which models you measure.** On GPQA Diamond the
frontier's top ten sit at 93% of the usable range while the open-community
leaderboard's top ten sit at 27% — 89% versus 59% saturation. Both are true and
they answer different questions. The headline reading prefers frontier
coverage, because "has this stopped separating the best models?" is usually
what's being asked, and the UI shows every source's reading rather than
averaging them into one misleading number.

**Reproducibility is measured for 4 benchmarks and guessed for 18.** Only MMLU,
GPQA Diamond, BBH and MATH Lvl 5 have two comparable sources. The rest fall
back to a curated count of how many groups publish scores — which says nothing
about whether those scores agree. Where both exist they can disagree sharply:
GPQA has five evaluators (proxy: fully reproducible) and 8.1 points of
unexplained scatter between two of them (measurement: not reproducible at all).

**Evaluator coverage is thin.** MirrorCode, which currently leads the rankings,
has exactly one independent evaluator, and seven more benchmarks have only two.
A benchmark nobody else has run is not the same as a benchmark everyone agrees
about.

**Model scoring is the weaker half.** The benchmark side is the point; the
model tab inherits every limitation above plus its own — VRAM estimates are
derived rather than measured, and nothing models the serving stack.

**The catalog is still one decision wide.** All twelve benchmarks from HF's
June 2024 retirement are now covered, which is what turned the backtest from
a pass into a partial failure. A second dated decision from another
leaderboard is the next thing that would tell you something new.

---

## Install and run

Requires Python 3.12 (pinned in `pyproject.toml`; `uv venv` will otherwise
happily pick an end-of-life system Python).

```bash
uv venv --python 3.12
uv pip install -r requirements.txt pytest
python app.py          # http://127.0.0.1:7860
pytest                 # 193 tests
```

The **benchmark tab works offline** from committed data. The **model tab** needs
`python fetch_models.py` first, and says so rather than inventing placeholders.

---

## Refreshing the data

All measured numbers come from data committed in `data/`. Nothing here hits the
network at runtime.

| source | refresh | needs | last pulled |
|---|---|---|---|
| Leaderboard score distributions | `python fetch_benchmark_scores.py` | `HF_TOKEN` | 2026-09-21 |
| Epoch AI benchmark export | manual download (see below) | — | 2026-09-14 |
| Hub model catalog | `python fetch_models.py` | `HF_TOKEN` | 2026-09-18 |
| Artificial Analysis catalog | `python enrich_scores.py` | `ARTIFICIAL_ANALYSIS_API_KEY` | 2026-09-18 |

Keys go in `.env` (gitignored) as `NAME=value`.

**Epoch AI** has no public API. Download the benchmark export from
[their data page](https://epoch.ai/benchmarks/use-this-data#download-this-data)
and copy the relevant CSVs into `data/epoch_benchmarks/`. Their data is CC-BY —
credit "Epoch AI, 'Capabilities & Benchmarking'. epoch.ai (2026)" wherever you
display it.

**Staleness matters here.** Saturation is a moving target: a benchmark measured
as healthy a year ago may be finished now. The committed distributions are the
project's evidence base, so a stale `data/` means stale conclusions, not just
stale numbers. `data/artificial_analysis.json` is gitignored — the free tier is
internal-use-only and not ours to redistribute.

---

## Layout

| file | purpose |
|---|---|
| [`fetch_benchmarks.py`](fetch_benchmarks.py) | The catalog: 26 benchmarks across 10 task categories, their curated fields, and the evidence dates behind each claim. |
| [`benchmark_scoring.py`](benchmark_scoring.py) | The four factors, the penalties, and as-of scoring for the backtest. |
| [`cross_source.py`](cross_source.py) | Do two evaluators agree about the same models? Offset vs scatter. |
| [`task_matcher.py`](task_matcher.py) | Free-text task description → benchmark category. |
| [`fetch_benchmark_scores.py`](fetch_benchmark_scores.py) | Pulls score distributions from HF leaderboards and EvalPlus. |
| [`backtest.py`](backtest.py) | Scores benchmarks as of a past date and checks against HF's June 2024 retirement. |
| [`scoring.py`](scoring.py) | Model scoring, weighted by benchmark trust. |
| [`fetch_models.py`](fetch_models.py), [`hardware_filter.py`](hardware_filter.py), [`device_profiles.py`](device_profiles.py) | The model side: Hub fetching, VRAM estimation, what each device can actually run. |
| [`app.py`](app.py) | Two tabs: which benchmark to trust, then which model to use. |

**Further reading:** [docs/METHODOLOGY.md](docs/METHODOLOGY.md) for how every
number is computed and what evidence standard it had to meet.
[docs/BACKTEST.md](docs/BACKTEST.md) for the one real test of whether any of
this works.
