# Saturation is measured wrong — design options

**Definition (2) was ADOPTED and IMPLEMENTED 2026-09-22.** The analysis
below is preserved as written; the implemented rule and its consequences
are at the end.

## IMPLEMENTED: top 20% of a stated population, minimum 30 models

**The percentile was chosen from the data, not preferred.** Across 20
cohort-vs-full-population pairs, mean |Δ| by band:

| band | min pop 10 | min pop 30 | min pop 50 | min pop 100 |
|---|---:|---:|---:|---:|
| top 1% | 0.113 | 0.103 | 0.095 | 0.096 |
| top 5% | 0.126 | 0.117 | 0.113 | 0.117 |
| top 10% | 0.111 | 0.093 | 0.092 | 0.088 |
| **top 20%** | **0.076** | **0.057** | **0.052** | **0.056** |
| top-10 (old) | 0.170 | 0.136 | 0.115 | 0.113 |

Top 20% is the most stable band **at every threshold tested**, by
roughly 2× over every alternative — so this is not a threshold artifact.
The tiebreak rule (choose whatever is closest to old top-10 behaviour on
large populations) did not apply, because no other band was equally
defensible.

**Minimum population 30**, from the same table: the largest improvement
step is 10 → 30, and it flattens after. Below 30, saturation is reported
as **unmeasurable** rather than estimated, and the drop-and-renormalize
rule then excludes it. This removes MirrorCode (8 models) and The Agent
Company (16) from measured saturation entirely.

**The population is part of the definition.** `SATURATION_TOP_PERCENTILE`
means nothing without saying *of what* — the top 20% of frontier models
and the top 20% of community submissions answer different questions, and
GPQA Diamond now reads 0.605 on the first and 0.088 on the second. The
explanation string names the population, and readings remain comparable
only within one.

### What it fixed, measured

The top-k-of-n artifact is gone: mean |Δ| between a fixed cohort and the
full population falls from **0.136 to 0.057**.

### What it did NOT fix — open work

1. **A benchmark's health still depends on who submits to its
   leaderboard.** An archived leaderboard yields a frozen reading; v1's
   six benchmarks still move by exactly zero because nothing is being
   added. The percentile makes the reading *stable*; it does not make it
   *independent of the submission pipeline*.
2. **`HEALTHY_SPREAD = 0.20` is now mis-calibrated.** It was set against
   top-10 spreads. A top-20% band reaches further down the distribution,
   so spreads are systematically wider and **every reading in the
   catalog fell** — mean |Δ| 0.297, max 0.604 (TruthfulQA 0.875 → 0.271).
   Relative ordering is largely preserved; absolute levels are not
   comparable to anything published before today. Retuning the constant
   is deliberately NOT done here: it would be a parameter change made
   while looking at test results.
3. **It interacts badly with drop-and-renormalize.** A benchmark below
   the minimum population loses discrimination, and the remaining
   factors are renormalized — so *less data can mean a higher score*.
   MirrorCode now tops the catalog at 95.1 on 1/3 factors. The
   thin-evidence display exists to make this visible; it does not make
   it right.

### The three reruns

| test | before | after | note |
|---|---|---|---|
| HF backtest | 10/12, gap −10.3 | **10/12, gap −28.9** | MATH Level 5 now the miss: 29 models at the cutoff, so its discrimination is dropped |
| Candidate 1 | FAIL, G−S −16.6 | **"PASS", G−S +4.1** | **does not count** — SWE-Bench rests on 1/3 factors, discrimination dropped |
| Hindcast | 1/7 discordant | **1/3 discordant** | still FAIL, still descriptive |

All three **supersede** their earlier results rather than contradicting
them: the old numbers were computed under a definition now known to be
artifactual.

## The problem in one sentence

`discrimination` is 50% of measurement health, and it is computed from
the top 10 of whatever models a source happens to have evaluated — so it
moves when the sample changes, with no change to the benchmark.

## The structural fact that makes this bad

> **Under the current definition, a fixed set of models has a constant
> saturation forever.** `measure_saturation` reads the top 10 of a list
> of (model, score) pairs. Those pairs never change once recorded.
>
> Therefore **100% of every temporal change in a saturation reading is
> population change.** Not "partly". All of it.

That is not necessarily wrong — a benchmark *should* look more saturated
once better models exist. The problem is that the metric cannot tell
apart two very different reasons the population changed:

1. **Real progress.** New, genuinely better models were released.
2. **Sampling.** The source decided to evaluate a different slice —
   Epoch adds frontier models; the HF leaderboard accepts whatever the
   community submits.

Both arrive as "new rows in a CSV", and the metric treats them
identically.

## How much is at stake — measured

Saturation computed on the **fixed cohort** of models that existed at
2024-06-01, against the reading on the **full population today**. The
benchmark is identical in both columns. Every difference is population.

| benchmark | source | n at T | n now | sat (cohort) | sat (all) | Δ |
|---|---|---:|---:|---:|---:|---:|
| **MATH Level 5** | Epoch | 29 | 108 | 0.123 | 0.938 | **+0.814** |
| **GPQA Diamond** | Epoch | 33 | 313 | 0.368 | 0.894 | **+0.526** |
| **GSM8K** | Epoch | 142 | 235 | 0.277 | 0.783 | **+0.506** |
| MATH Level 5 | v2 | 608 | 4,575 | 0.202 | 0.507 | +0.305 |
| BIG-Bench Hard | Epoch | 81 | 92 | 0.247 | 0.483 | +0.236 |
| **MMLU-Pro** | v2 | 608 | 4,575 | 0.594 | 0.374 | **−0.220** |
| **MuSR** | v2 | 608 | 4,575 | 0.644 | 0.440 | **−0.205** |
| MMLU | Epoch | 172 | 249 | 0.612 | 0.817 | +0.204 |
| Winogrande | Epoch | 124 | 145 | 0.543 | 0.641 | +0.099 |
| ARC | Epoch | 121 | 142 | 0.626 | 0.528 | −0.098 |
| IFEval | v2 | 608 | 4,575 | 0.717 | 0.814 | +0.097 |
| BBH / GPQA / HellaSwag (v2, Epoch) | — | — | — | — | — | ≤0.05 |
| MMLU, GSM8K, HellaSwag, TruthfulQA, ARC, Winogrande | **v1** | 7,184 | 7,260 | — | — | **0.000** |

**Mean |Δ| across 20 readings: 0.170. Maximum: 0.814. Eight readings move
more than 0.10 on population alone.**

Two things to notice:

- **The v1 rows move by exactly zero.** v1 was archived, so its
  population stopped growing, so its saturation froze. A benchmark's
  measured health now depends on whether anyone is still submitting to
  the leaderboard that scores it.
- **The sign is not consistent.** Epoch's additions are frontier models,
  which push saturation *up* (MATH +0.814). The v2 leaderboard's
  additions are mostly weaker community models, which push it *down*
  (MMLU-Pro −0.220, MuSR −0.205) by widening the top-10 spread. **Whether
  a benchmark looks better or worse over time is partly a fact about the
  source's submission policy.**

### The mechanism, decomposed

Both saturation terms are fractions of the usable range:

| benchmark / source | spread (cohort → all) | headroom used (cohort → all) |
|---|---|---|
| MATH Level 5 / Epoch | 0.266 → **0.016** | 0.352 → **0.974** |
| GPQA Diamond / Epoch | 0.114 → 0.025 | 0.251 → 0.927 |
| GSM8K / Epoch | 0.224 → 0.058 | 0.791 → 0.918 |
| MMLU-Pro / v2 | 0.070 → **0.151** | 0.491 → 0.612 |
| MuSR / v2 | 0.024 → **0.099** | 0.211 → 0.323 |

MATH Level 5's top-10 spread collapses from 0.266 (above the 0.20
"healthy" threshold) to 0.016 as frontier models pile up at the ceiling —
a real finding. MMLU-Pro's spread *triples* as community models fill in
below the leaders — which reads as "less saturated" but is really "more
weak models were sampled".

## Candidate definitions

### (1) Fixed cohort

Pick a model set once and always measure on it.

- **Requires:** a cohort definition and a policy for when to roll it
  forward. Rolling it forward is the whole problem again, one level up.
- **Breaks:** the benchmark can never be observed to saturate, since the
  cohort's scores never change. It measures "was this benchmark
  discriminating among 2024 models?" forever. Useless as a live signal;
  **ideal as a controlled comparison**, which is what the table above is.
- **Data:** available for 20 readings (any source with ≥10 dated models
  before a chosen T).

### (2) Fixed percentile within a defined population

Replace "top 10" with, say, "the 90th–99th percentile of models in
population P", with P stated.

- **Requires:** stating P — which is the population-disclosure work
  already done in `BenchmarkScores.population`. No new parameter beyond
  the percentile band, which replaces the existing `SATURATION_TOP_K`
  rather than adding to it.
- **Fixes:** the n-dependence of "top 10". Top 10 of 33 models is the top
  30%; top 10 of 4,575 is the top 0.2%. **That alone explains a large
  part of the GPQA Epoch-vs-v2 gap**, and it is a pure artifact.
- **Breaks:** small populations. The 90th percentile of 29 models is
  three models. Needs a minimum-n rule.
- **Data:** every benchmark with ≥~30 scores; 25 of 26 qualify on at
  least one source.

### (3) Top-k among models meeting a stated bar

E.g. "models released in the last 12 months" or "models above X on a
reference benchmark".

- **Requires:** the bar. A date bar needs per-model release dates —
  available for Epoch and v1/v2 but *not* for EvalPlus (zero dated
  models), so HumanEval drops out entirely.
- **Fixes:** the "frozen leaderboard" problem — a benchmark whose source
  stopped collecting would show as stale rather than frozen.
- **Breaks:** it imports a second benchmark's judgement if the bar is
  score-based, which is circular.
- **Data:** 25 of 26 have dated models on at least one source; HumanEval
  has none.

### (4) Report the trajectory instead of the level

Stop asking "how saturated is it?" and report "how fast is the top 10
converging, per unit of population growth?"

- **Requires:** no new parameter; it is the derivative of what is already
  computed.
- **Fixes:** the mean-reversion artifact that made the hindcast
  uninterpretable.
- **Breaks:** it is no longer a 0–1 factor that slots into a weighted sum
  without a new normalization — which *would* be a new parameter.
- **Data:** needs ≥2 dated snapshots: the 14 readings above with non-zero
  growth.

## Which benchmarks can support which

| definition | benchmarks with enough data |
|---|---|
| (1) fixed cohort | 13 benchmarks / 20 readings |
| (2) fixed percentile | 25 of 26 (all but LiveCodeBench) |
| (3) bar-gated top-k | 25 of 26; **HumanEval excluded** — EvalPlus publishes no dates |
| (4) trajectory | 13 benchmarks with ≥5 new models since T |

## What this implies for the tests already run

**The backtest is less affected than it looks.** It scores as of
2024-06-01 using only pre-cutoff models, which is definition (1) — a
fixed cohort — applied consistently to all twelve. Its *internal*
comparison is therefore population-controlled. What it cannot claim is
that those saturation values mean the same thing as today's.

**The hindcast is invalidated by this, and already said so.** Its
outcome variable was saturation at a later date on a population that had
grown sevenfold. Given the structural fact above, the outcome it measured
was *definitionally* population change. Its −0.971 mean-reversion
correlation is this document's headline finding arriving from the other
direction.

**Candidate 1 is affected and this was not previously noted.** It
compared SWE-Bench Verified (18 dated models before the as-of date)
against GPQA Diamond (196). Top 10 of 18 is the top 56%; top 10 of 196 is
the top 5%. **The two sides of that comparison were not measuring the
same thing**, and definition (2) would have removed the artifact. This
does not change the verdict — specificity, not discrimination, drove that
failure — but the discrimination contribution of +2.02 should not be
relied on.

## Recommendation for how to decide

Definition (2) is the only one that fixes a *pure artifact* (top-k of n
depends on n) without inventing a parameter or losing the live signal.
(1) is a measurement tool, not a scoring definition. (4) is the most
honest about what the data supports and the most disruptive to the
factor structure.

None of them fix the deeper issue: **what a benchmark's saturation "is"
depends on who you think should be able to solve it**, and that is a
choice, not a measurement. Whatever is chosen should be stated in the UI
next to the number, the way the population now is.
