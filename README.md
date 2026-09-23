# Benchmark Recommender

**An evidence dossier on 28 LLM benchmarks.** For each one: what has been
measured, what was read out of a paper and by whom, when each claim became
public, and — stated as plainly as the rest — what nobody has established.

The premise is still that popularity is not evidence a benchmark works.
Labs optimize against well-known benchmarks until the leaderboard stops
separating models, and public test sets leak into training data. The
project's answer to that is **the per-benchmark evidence**, not the
composite score.

## What this establishes, and what it does not

**Established, and reproducible from the committed data:**

- **Measured saturation** for 23 of 28, computed from real score
  distributions, each labelled with the model population it was measured
  on and the number of models behind it.
- **Cross-source agreement** for 8 of 28 — the same models scored by two
  evaluators, split into a systematic offset and irreproducible scatter.
- **Contamination and item-quality audits** for the benchmarks where a
  study exists, each carrying a *basis*: whether an error rate is an
  estimate or a demonstrated floor, whether a contamination effect
  controlled for difficulty or did not.
- **A date on every curated claim**, which is what allows a benchmark to
  be scored as it would have looked in the past without using evidence
  from the future.
- **What nobody has checked**, marked in the entry rather than omitted.

**NOT established — the composite score does not rank benchmarks better
than release date does.** Three tests have been run to a conclusion:

| test | result |
|---|---|
| **HF retirement backtest** (June 2024, 12 benchmarks) | **RETIRED 2026-09-22 as a discriminating test.** On the 30 comparisons that are actually valid the scorer gets 30/30 — **and so does sorting by release date.** It cannot separate them and never will: that is a property of these twelve benchmarks. Kept as a regression check. |
| **Candidate 1** (OpenAI abandons SWE-Bench Verified) | **Not a valid comparison.** The two benchmarks are in different evidence tiers — 18 models against 196. Exhausted as a test. |
| **Hindcast** (does trust at T predict later saturation?) | 2 of 4 discordant pairs — a coin flip. Declared descriptive before it was run. |

On the backtest's twelve benchmarks, measured 2026-09-23
(`python probes/findings.py correlations`):

- **Release date predicts HF's retire/keep decision at r = −0.793.** The
  composite health score predicts it at **+0.502** and measured
  saturation at **−0.198**. Age predicts the decision better than the
  score built to predict it.
- **Measured saturation alone scores 6/12 on the backtest — exactly
  chance.** Freshness alone, the age-derived factor, scores 10/12 and
  loses separation by 6.3 points against the full scorer's 26.9
  (`python backtest.py --sweep`).

> ⚠️ **Do not quote the backtest's 30/30.** The baseline it is meant to
> beat scores identically, and the pairs that would have separated them
> were excluded as invalid. Citing that number as vindication would be
> the most misleading thing this project could say about itself. See
> [docs/BACKTEST.md](docs/BACKTEST.md).

> **And do not read the negative results as proof the scoring is
> useless either.** HF's retirement decision is a human judgement that
> is *itself* heavily age-correlated — a leaderboard retires old
> benchmarks — so a test scored against it cannot separate "measured
> saturation is uninformative" from "measured saturation is informative
> about something this decision did not turn on". **The backtest can
> show that the scorer has not been shown to beat a calendar. It cannot
> show that measured saturation is useless.** Both statements are in
> this README because leaving either out would overstate something.

**The project's only live validation is the
[forward test](docs/FORWARD_TEST.md)**, sealed 2026-09-22 and maturing
**2028-09-22**, with its age baseline fixed in advance. It is the only
test here whose outcome has not already happened, and therefore the only
one that cannot be gamed. [ARC-AGI-1](docs/ARC_AGI_TEST.md) was scoped
as a second candidate and **rejected**: only 4 of its 75 available
models predate the window the test would need. Until the forward test
returns, the honest answer to "does the scoring work?" is **no test has
shown that it does.**

### The numbers move when the constants do

Seven of the nine tunable parameters reorder the catalog across their
defensible ranges. This is published here rather than buried because it
bounds what any ranking on this page can mean:

| parameter | range tested | benchmarks that change rank (of 28) |
|---|---|---:|
| `HEALTHY_SPREAD` | 0.084 – 0.358 | **19** |
| `SATURATION_TOP_PERCENTILE` | 10% – 30% | **15** |
| `MIN_SATURATION_POPULATION` | 10 – 50 | **13** (3 change tier) |
| `LEAKAGE_HALF_LIFE_DAYS` | 365 – 1460 | 8 |
| `FULL_CONTAMINATION_RATE` | 0.15 – 0.50 | 6 |
| `CONTAMINATION_PENALTY` | 0.50 – 0.80 | 5 |
| `SCATTER_TOLERANCE` | 0.04 – 0.16 | 5 |
| `ITEM_ERROR_PENALTY` | 0.40 – 0.80 | 3 |
| `FULL_ITEM_ERROR_RATE` | 0.10 – 0.40 | 3 |

`HEALTHY_SPREAD` is the worst: across its range mean catalog health
moves **58.8 → 45.5**. It was derived on 2026-09-22 from the measured
cross-source noise floor — 3 × the maximum measured scatter (0.0805) =
0.24 — and **the multiplier 3 is an invented choice**, named here and not
only in the commit. No derivation of that constant escapes one such
choice; anchoring on the observed spread distribution instead just moves
it to a quantile.

**So: the dossier is the product and the score is a summary of it.** The
ranking is grouped by how much evidence each score rests on, and scores
are comparable only within a group. If that sounds like a smaller claim
than "which benchmark should you believe" — it is, and it is the one the
evidence supports today.

### The concrete case, stated as evidence rather than a ranking

**HumanEval**, every figure re-measured 2026-09-22:

| | |
|---|---|
| released | 2021-07-07 — 164 short functions, public and static since |
| measured saturation | **0.438**, over **125 code models submitted to EvalPlus** |
| contamination rate | **13%** of items found in a major pretraining corpus |
| contamination effect | scores fall **39.4%** on EvoEval — **basis: uncontrolled**, because EvoEval does not hold difficulty constant, so part of that drop is the new problems being harder |
| item quality | **never audited** — `None`, which here means nobody looked, not that it is clean |
| measurement health | **28.1**, resting on **2 of 3 factors**; its reproducibility is unmeasurable because only one source covers it |

That is the thesis without a ranking: a benchmark everyone quotes, whose
leakage is measured, whose contamination effect cannot be cleanly
separated from difficulty, and whose answer key nobody has checked.

> **Superseded headline, kept rather than deleted.** This section used to
> read *"HumanEval's measurement health is 32.6/100 and MirrorCode's is
> 95.1"*. That comparison is dead twice over: the number moved, and the
> two benchmarks are in **different evidence tiers** — MirrorCode's score
> rests on a release date, from 8 scored models with no measurable
> saturation — so they are not ranked against each other.
> **This project does not make claims that compare benchmarks across
> evidence tiers.** See [docs/RANK_RANGES.md](docs/RANK_RANGES.md).

---

## What you can and can't trust here

This matters more than the scores, so it comes first.

**Measured** — computed from real score distributions, reproducible from the
committed data:

| | coverage |
|---|---|
| Saturation (the `discrimination` factor) | 23 of 28 benchmarks |
| Cross-source agreement (`reproducibility`) | 8 of 28 |

**Curated** — read out of papers and reports by a human, cited in each entry's
`curation_notes` with a date:

| | coverage |
|---|---|
| Contamination rate (fraction of items in pretraining corpora) | 3 of 28 |
| Contamination *effect* (score drop on a fresh set) | 2 of 28 |
| Contamination flagged but never quantified — **no penalty** | 13 of 28 |
| Item error rate (wrong answer keys, broken tests) | 4 of 28 |
| Release dates, dataset sizes, holdout type | all 28 |

**Judgement calls** — defensible, argued in comments, but mine rather than
anybody's finding:

- `task_specificity` for all 28 benchmarks, now computed from a
  [five-dimension rubric](docs/SPECIFICITY_RUBRIC.md) stored per benchmark
  rather than assigned as a bare number. **This makes it auditable
  judgement, not measurement** — five judgements have replaced one, and
  neither the rubric nor any score against it has been checked by a second
  reviewer.
- `independent_evaluators` for the 18 benchmarks where agreement can't be
  measured. Winogrande's 4 and GSM8K's 5 are partly unsourced: three of
  each can be named, the rest cannot. **Since 2026-09-22 this count no
  longer enters any score** — an unmeasurable factor contributes nothing —
  but it is still shown.
- Every weight and threshold: the 0.50/0.25/0.25 health split, the two-year
  leakage half-life, the penalty curves. `HEALTHY_SPREAD` was derived from
  the measured noise floor on 2026-09-22 (0.24) after seven months of being
  a chosen number; **its defensible range is 0.084–0.358, across which mean
  catalog health moves 12 points (56.2 → 43.8) and up to 19 of 28
  benchmarks change rank.**

The UI reports `measured` / `curated` / `unknown` per factor, per benchmark,
groups the ranking by evidence tier, and names the model population behind
every saturation reading. If a number traces back to a guess, the guess is
visible.

**Saturation figures this project published before 2026-09-22 are on a
different scale** — the definition changed from a fixed top-10 to the top
20% of a stated population, and every reading fell (mean |Δ| 0.297). Old
and new saturation numbers are not comparable.

---

## Limitations

The ones that undercut the project, stated plainly:

**The composite score has never been shown to beat a calendar.** The
health weights (0.50 discrimination / 0.25 freshness / 0.25
reproducibility) are a proportional rescaling of uncalibrated judgement
calls. On the backtest's 30 valid comparisons the scorer gets 30/30 —
and so does sorting by release date, so the test cannot tell them apart.
Candidate 1 turned out not to be a valid comparison at all. The hindcast
returned a coin flip. **No weight was ever changed in response to any of
these**, and the [forward test](docs/FORWARD_TEST.md) is sealed to find
out whether the scoring means anything.

**A score can rest on one factor or three, and the highest score in the
catalog rests on one.** Unmeasurable factors contribute nothing and the
rest are renormalized, which makes a thin score arithmetically
comparable to a thick one — which it is not. Evidence tiers stop the
comparison: 8 benchmarks are full evidence, 15 partial, 3 thin, and the
ranking never crosses a tier. MirrorCode scores 95.1 and ranks below all
23 benchmarks above its tier.

**Saturation depends on which models you measure, and the ranking spans
four populations.** 25 of the 28 have a score source at all, read on
Epoch (20), the v2
leaderboard (3), v1 (1) and EvalPlus (1). **18 pairs in the catalog change
order depending on which population is used** — MATH Level 5 alone moves
17.2 points between its two readings and flips against 9 other
benchmarks. The UI now names the population on every row and warns when a
table spans more than one, but the headline single-number ranking is
still not a like-for-like comparison.

**Saturation depends on which models you measure.** On GPQA Diamond the
frontier's top ten sit at 93% of the usable range while the open-community
leaderboard's top ten sit at 27% — 89% versus 59% saturation. Both are true and
they answer different questions. The headline reading prefers frontier
coverage, because "has this stopped separating the best models?" is usually
what's being asked, and the UI shows every source's reading rather than
averaging them into one misleading number.

**Reproducibility is measured for 6 benchmarks and guessed for 20.** Only MMLU,
GPQA Diamond, BBH, MATH Lvl 5, Winogrande and GSM8K have two comparable
sources. The rest fall back to a curated count of how many groups publish
scores — which says nothing about whether those scores agree. Where both exist
they can disagree sharply: GPQA has five evaluators (proxy: fully reproducible)
and 8.1 points of unexplained scatter between two of them (measurement: not
reproducible at all).

**And the backtest cannot use the measurement at all.** Cross-source agreement
is computed from today's score sets, so as-of scoring falls back to the curated
count — meaning the one test this project has runs on the guessed value for all
twelve. GSM8K is the worst case: an unsourced count of 5 hands it *full* marks
for reproducibility in 2024, while the measurement available today says 0.134
(6.9 points of scatter plus a 7.0-point systematic gap between harnesses).

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
pytest                 # 219 tests
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
| [`fetch_benchmarks.py`](fetch_benchmarks.py) | The catalog: 28 benchmarks across 10 task categories, their curated fields, and the evidence dates behind each claim. |
| [`benchmark_scoring.py`](benchmark_scoring.py) | The four factors, the penalties, and as-of scoring for the backtest. |
| [`cross_source.py`](cross_source.py) | Do two evaluators agree about the same models? Offset vs scatter. |
| [`task_matcher.py`](task_matcher.py) | Free-text task description → benchmark category. |
| [`fetch_benchmark_scores.py`](fetch_benchmark_scores.py) | Pulls score distributions from HF leaderboards and EvalPlus. |
| [`backtest.py`](backtest.py) | Scores benchmarks as of a past date and checks against HF's June 2024 retirement. |
| [`scoring.py`](scoring.py) | Model scoring, weighted by benchmark trust. |
| [`fetch_models.py`](fetch_models.py), [`hardware_filter.py`](hardware_filter.py), [`device_profiles.py`](device_profiles.py) | The model side: Hub fetching, VRAM estimation, what each device can actually run. |
| [`app.py`](app.py) | Two tabs: the benchmark dossier and ranking, then the model view. |

**Start here:** [docs/FINDINGS.md](docs/FINDINGS.md) — the standalone
write-up of what this project has established and what it has not, for a
reader who has never seen the repository. Every figure in it is footnoted
with the command that reproduces it; `python probes/findings.py` runs them
all.

**Then:** [docs/METHODOLOGY.md](docs/METHODOLOGY.md) for how every
number is computed and what evidence standard it had to meet.
[docs/BACKTEST.md](docs/BACKTEST.md) for the one real test of whether any of
this works, and why it was retired. [docs/BACKTEST_DESIGN.md](docs/BACKTEST_DESIGN.md)
for what that test can and cannot establish. [docs/POPULATION_CLIFF.md](docs/POPULATION_CLIFF.md)
for the 30-model threshold, which is a cliff rather than a taper.

On the twelve benchmarks of the retirement test, measured 2026-09-22
(`python probes/findings.py correlations`): release date predicts HF's
retire/keep decision at **r = −0.793**, the composite health score at
**+0.502**, and measured saturation at **−0.198**. **Age predicts the
decision better than the score built to predict it.**
