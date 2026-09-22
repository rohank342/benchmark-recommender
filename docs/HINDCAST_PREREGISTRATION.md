# Hindcast — pre-registration

**Status: design only. Nothing has been run.** No outcome — no saturation
at any date later than T — has been computed for any benchmark in this
document. Awaiting the owner's approval.

## The question

> Does trust as of date **T** predict measured discrimination at a later
> date better than **age** does?

This is a different question from the backtest. The backtest asks whether
the scorer agrees with a decision HF made. This asks whether the scorer
**predicts the future**, which is the claim the tool actually makes when
it tells someone a benchmark is worth using.

---

## THE HEADLINE PROBLEM, before any design detail

**This is not independent evidence.** After applying the eligibility and
population rules below, the surviving set is **five benchmarks — all six
of the v2 "kept" half of the existing backtest, minus one.** The hindcast
reuses the same benchmarks, the same score data and the same as-of date as
the test it is meant to corroborate.

It can still falsify: if the scorer cannot predict later saturation on
benchmarks it has already been scored against, that is damning. It cannot
corroborate: a pass would tell us the scorer works on the only five
benchmarks anyone has looked at.

**And the discordant-pair count is 7** (details below). Seven binary
comparisons, dominated by two benchmarks. This test is the same size as
everything else in this project.

---

## Design

### T — the prediction date

**T = 2024-06-01**, the same cutoff as the backtest.

The data does not support a better one. The two sources with dated model
populations are HF's Open LLM Leaderboard v1 (archived June 2024) and v2
(archived 2025-03-13). A later T would leave v2 with almost no
post-T population to measure an outcome against; an earlier T predates v2
entirely. T = 2024-06-01 is where v2's population is smallest (608) and
its later population largest (4,046), which is the only configuration
that gives the outcome room to move.

### Outcome date and its honest name

**The outcome date is the latest date in the v2 population, which is
effectively 2025-03-13** — when the leaderboard was archived. This is a
**nine-month** horizon, not "today". Nothing in v2 is newer than that, so
the hindcast cannot say anything about 2026 models.

### POPULATION — fixed in advance

**Open LLM Leaderboard v2, raw (un-rescaled) columns, for every benchmark
at both dates.** 608 models at T, 4,046 at the outcome date, *identical
sets for all six benchmarks*.

**Why this and not the obvious alternative.** The tempting design is
"use each benchmark's primary source", which yields 8 benchmarks instead
of 5. It is wrong, and it is wrong in a way this project has already been
bitten by: it would compare MATH Level 5's saturation among Epoch's
frontier models against MuSR's among the open-community leaderboard.
GPQA Diamond reads 89% saturated on one and 59% on the other
(CLAUDE.md §7). A pairwise comparison across mismatched populations
measures the population difference, not the benchmarks.

v2 is the only source where every eligible benchmark shares one model
population at both dates. That costs three benchmarks and buys the only
version of this test that measures what it claims to.

### Eligibility

Required: dated score distributions in the v2 population at both T and
the outcome date, ≥10 models at T (the `SATURATION_TOP_K` minimum), and
≥20 new models by the outcome date.

| benchmark | released | in? | why not |
|---|---|:-:|---|
| MATH Level 5 | 2021-03-05 | ✓ | |
| BIG-Bench Hard | 2022-10-17 | ✓ | |
| MuSR | 2023-10-24 | ✓ | |
| GPQA Diamond | 2023-11-20 | ✓ | |
| MMLU-Pro | 2024-06-03 | ✓ | |
| IFEval | 2023-11-14 | ✗ | already 0.717 saturated at T — ceiling rule |
| MMLU, GSM8K, TruthfulQA, ARC, HellaSwag, Winogrande | 2018–2021 | ✗ | v1 only; v1 was archived at T, so there is no post-T population |
| TriviaQA | 2017 | ✗ | 3 new models since T |
| HumanEval | 2021 | ✗ | EvalPlus publishes no dates at all |
| LiveCodeBench | 2024 | ✗ | no fetchable score export |
| SWE-Bench, MirrorCode, Terminal Bench, GSO, DeepSWE, FrontierCode, OSWorld, The Agent Company, HLE, SimpleQA Verified, Aider polyglot | 2024–2026 | ✗ | zero models at T — released at or after it |

**Five eligible benchmarks.**

### Outcome measure, and the ceiling problem

**Outcome = measured saturation LEVEL at the outcome date.** Decided in
advance, with the reasoning:

- The claim the tool makes is about the later *level* — "will this still
  discriminate in a year?" — not about the size of a move.
- A benchmark already saturated at T can only stay saturated. Every
  predictor gets those pairs right for free, which inflates all of them
  equally and adds no information about which is better.

So the ceiling is handled by **excluding any benchmark already ≥0.70
saturated at T**, rather than by switching to change-in-saturation. That
rule removes IFEval (0.717) and nothing else. Threshold fixed now.

*Change in saturation will be reported as a secondary diagnostic, clearly
labelled, because it is a different question with its own asymmetry — a
benchmark at 0.12 has ten times the room to move that one at 0.64 has.*

### Predictors

All three computed as of T, using only evidence available then:

1. **Full as-of trust** — the four weighted factors plus penalties.
2. **Discrimination only** — the measured saturation factor alone.
3. **Release-date order** — the baseline. Older predicts more saturated
   later.

### The five, as of T

| benchmark | released | trust @ T | discrimination @ T | saturation @ T |
|---|---|---:|---:|---:|
| MATH Level 5 | 2021-03-05 | 71.6 | 0.877 | 0.123 |
| GPQA Diamond | 2023-11-20 | 65.9 | 0.632 | 0.368 |
| BIG-Bench Hard | 2022-10-17 | 63.5 | 0.753 | 0.247 |
| MMLU-Pro | 2024-06-03 | 52.2 | 0.406 | 0.594 |
| MuSR | 2023-10-24 | 42.4 | 0.356 | 0.644 |

These are predictions, not outcomes. No later-date saturation has been
computed.

---

## Primary metric and the discordant-pair count

**Metric:** among pairs where the scorer and the age baseline predict
**opposite** orderings of later saturation, the fraction where the scorer
is right.

A pair is discordant when the **older** benchmark is ranked **better** by
the scorer — the two predictors then disagree about which will be more
saturated later. Concordant pairs are excluded because they cannot
distinguish the predictors, for the same reason bad candidate events were
dropped in `SECOND_TEST_PREREGISTRATION.md`.

**Computed before any outcome (this needs only as-of predictions):**

| predictor | pairs | discordant vs age |
|---|---:|---:|
| full trust | 10 | **7** |
| discrimination only | 10 | **8** |

The seven discordant pairs for full trust:

| older, ranked better by the scorer | newer, ranked worse |
|---|---|
| MATH Level 5 | MMLU-Pro |
| MATH Level 5 | GPQA Diamond |
| MATH Level 5 | BIG-Bench Hard |
| MATH Level 5 | MuSR |
| BIG-Bench Hard | MMLU-Pro |
| BIG-Bench Hard | MuSR |
| GPQA Diamond | MMLU-Pro |

### Is 7 enough to mean anything? No.

Stated now, as required, because it is a finding rather than a detail.

- **7 binary comparisons.** A coin flip scores 4/7 on average. Getting
  6/7 by chance has probability ≈ 0.06; 7/7 ≈ 0.008.
- **They are not independent.** MATH Level 5 appears in 4 of the 7 and
  BIG-Bench Hard in 3. If MATH Level 5's later saturation goes one way,
  four of the seven move together. The effective sample size is closer to
  **two or three** than to seven.
- **MATH Level 5's trust at T rests on 29 models** in the Epoch
  population and its v2 column at T on 608 — but its 71.6 is the highest
  score in the set, so the benchmark that dominates the test is also the
  one with the least-supported prediction.

**Conclusion, pre-registered: this hindcast cannot validate the scorer.**
It is registered as a falsification check only, on the same terms as
Candidate 1. A pass must be reported as "survived a test it could have
failed", never as evidence the scorer predicts saturation.

---

## Pass threshold — fixed now

- **PASS:** the scorer is right on **≥ 6 of 7** discordant pairs (≈0.86).
- **FAIL:** **≤ 3 of 7**. The scorer is worse than a coin flip on the
  pairs built to separate it from age.
- **INCONCLUSIVE:** 4 or 5 of 7. Reported as inconclusive, not spun
  either way.

6/7 is chosen because 5/7 (≈0.71) has a one-sided p of about 0.23 against
a coin — indistinguishable from luck at this size. Even 6/7 is p ≈ 0.06,
which is why a pass is not validation.

**Secondary, reported but not part of pass/fail:**
- the same metric for discrimination-only across its 8 discordant pairs;
- Spearman correlation between each predictor and later saturation across
  all five benchmarks;
- change-in-saturation as an alternative outcome.

---

## What would count as evidence AGAINST the scorer

1. **≤ 3 of 7 discordant pairs correct.** The scorer would be
   anti-predictive on exactly the comparisons where it disagrees with the
   calendar. Given Candidate 1 already failed and the backtest does not
   beat age, this would close the question for the current design.
2. **Discrimination-only beating full trust.** If the measured factor
   alone predicts better than the weighted combination, the other three
   factors are subtracting information. Candidate 1 already showed
   specificity overriding discrimination 8:1 in the wrong direction; a
   repeat here would make that a pattern rather than an incident.
3. **Age beating both on the concordant pairs too.** Reported alongside,
   because if the baseline is better everywhere, the discordant-pair
   framing is flattering the scorer by construction.
4. **A result that depends entirely on MATH Level 5.** If dropping the
   single benchmark that appears in 4 of 7 pairs changes the verdict, the
   test measured one benchmark, not a scorer — and that must be reported
   as the finding rather than buried in a footnote.
5. **Any need to change the design after seeing an outcome.** As with
   Candidate 1: the honest report is "the design failed", not a revised
   design.

---

## What was inspected while writing this

- **Looked at:** release dates, as-of trust and discrimination at T,
  saturation at T, and model counts at both dates. All of these are
  predictor-side or population-size quantities.
- **Not looked at:** saturation, scores, or any distribution at the
  outcome date for any of the five benchmarks. That is the outcome, and
  it stays uncomputed until this design is approved.
