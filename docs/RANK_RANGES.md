# Rank ranges — a single rank implies precision the method lacks

**Design only. Nothing built.** Measured 2026-09-22 over all 28
benchmarks.

Seven of nine tunable parameters reorder the catalog across their
defensible ranges. This asks the obvious follow-up: **if each benchmark
has a rank *range* rather than a rank, how wide is it, and which claims
survive?**

## Method

Each parameter was varied one at a time across its defensible range
(the same ranges published in the README), the catalog re-ranked, and
each benchmark's best and worst position recorded. **One at a time, not
jointly** — see the limitation below.

| parameter | values tested |
|---|---|
| `HEALTHY_SPREAD` | 0.084, 0.139, 0.24, 0.282, 0.358 |
| `SATURATION_TOP_PERCENTILE` | 10, 20, 30 |
| `MIN_SATURATION_POPULATION` | 10, 30, 50 |
| `LEAKAGE_HALF_LIFE_DAYS` | 365, 730, 1460 |
| `FULL_CONTAMINATION_RATE` | 0.15, 0.30, 0.50 |
| `CONTAMINATION_PENALTY` | 0.50, 0.65, 0.80 |
| `SCATTER_TOLERANCE` | 0.04, 0.08, 0.16 |
| `ITEM_ERROR_PENALTY` | 0.40, 0.60, 0.80 |
| `FULL_ITEM_ERROR_RATE` | 0.10, 0.20, 0.40 |

## Results

| benchmark | rank | best | worst | span |
|---|---:|---:|---:|---:|
| Winogrande | 1 | 1 | 3 | **2** |
| BIG-Bench Hard | 2 | 1 | 3 | **2** |
| ARC | 3 | 2 | 3 | **1** |
| GSM8K | 4 | 4 | 6 | **2** |
| MATH Level 5 | 5 | 4 | 8 | 4 |
| MMLU | 6 | 5 | 8 | 3 |
| HellaSwag | 7 | 5 | 8 | 3 |
| GPQA Diamond | 8 | 5 | 8 | 3 |
| MuSR | 9 | 9 | 12 | 3 |
| SimpleQA Verified | 10 | 10 | 14 | 4 |
| Humanity's Last Exam | 11 | 9 | 12 | 3 |
| OSWorld | 12 | 10 | 15 | 5 |
| Terminal Bench | 13 | 13 | 17 | 4 |
| **GSO-Bench** | 14 | 9 | 24 | **15** |
| IFEval | 15 | 14 | 17 | 3 |
| **MMLU-Pro** | 16 | 10 | 19 | **9** |
| **FrontierCode** | 17 | 9 | 22 | **13** |
| Aider polyglot | 18 | 15 | 20 | 5 |
| TruthfulQA | 19 | 17 | 20 | 3 |
| DeepSWE | 20 | 18 | 21 | 3 |
| HumanEval | 21 | 19 | 23 | 4 |
| SWE-Bench Verified | 22 | 21 | 26 | 5 |
| TriviaQA | 23 | 20 | 24 | 4 |
| MirrorCode | 24 | 21 | 25 | 4 |
| LiveCodeBench | 25 | 23 | 26 | 3 |
| The Agent Company | 26 | 18 | 26 | **8** |
| DS-1000 | 27 | 27 | 27 | **0** |
| MBPP | 28 | 28 | 28 | **0** |

### Stable

**Winogrande, BIG-Bench Hard, ARC, GSM8K** (spans 1–2) — all
full-evidence tier, all with measured saturation over large populations.
More evidence produces a more stable rank, which is the tiering argument
arriving from a different direction.

**DS-1000 and MBPP** have span 0 for an uninteresting reason: they are
thin-tier with no score data, so no saturation parameter touches them.
**A stable rank is not automatically a trustworthy one.**

### Unstable

| benchmark | span | why |
|---|---:|---|
| **GSO-Bench** | 15 | 38 models — near `MIN_SATURATION_POPULATION`, so it crosses in and out of measurability, changing tier |
| **FrontierCode** | 13 | 35 models, same reason |
| **MMLU-Pro** | 9 | 4,575 models; the percentile choice moves it a long way |
| **The Agent Company** | 8 | 16 models — below the minimum today, above it at a minimum of 10 |

**The instability clusters at the population minimum.** Three of the four
sit within a few models of 30, where a parameter change flips them
between tiers. That is a real property of the design, not noise: the
minimum is a cliff, and benchmarks near it have no stable position.

## Which README claims survive

| claim | survives? |
|---|---|
| "HumanEval's health is 32.6" | **No** — 28.1 today after this session's changes, and its rank spans 19–23. The *number* should not be quoted at all. |
| "HumanEval ranks below MirrorCode" | **No longer meaningful** — they are in different evidence tiers and are not ranked against each other. |
| "MirrorCode scores highest and ranks in the thin tier" | **Yes** — true across every parameter setting tested. |
| "Winogrande leads the full-evidence tier" | **Mostly** — rank 1–3; BIG-Bench Hard overtakes it at high `HEALTHY_SPREAD`. |
| "GPQA Diamond ranks last of the full tier" | **Yes** — 5–8, always within the full tier and always in its lower half. |
| "23 of 28 have measured saturation" | **Parameter-dependent** — at `MIN_SATURATION_POPULATION = 50` it is fewer. |

**The surviving claims are all about tiers and directions, not
positions.** That is the shape a defensible claim has here.

## How the UI could show a range

```
  🟩 FULL EVIDENCE
     Winogrande          59.0   rank 1–3    ████▏
     BIG-Bench Hard      55.6   rank 1–3    ███▉
     ARC                 53.1   rank 2–3    ███▊
```

A bar with a shaded uncertainty band, and the rank shown as a span. The
cost is that "rank 1–3" for three benchmarks says they are not ordered
against one another — which is true and is what the current display
hides.

### The headline under ranges

The README's old pairing is dead twice over — different tiers, and
HumanEval's number moved. The honest version:

> **HumanEval** — partial evidence, health 28.1, rank 19–23 of 28.
> **MirrorCode** — thin evidence, health 95.1, rank 21–25, and its score
> rests on a release date.
>
> Both sit in the lower half however the constants are set. Neither
> number should be read to one decimal place, and they are not ranked
> against each other.

Less quotable, and the part that is actually established.

## Limitation: one parameter at a time

**Joint variation is feasible but was not run.** Nine parameters at
three values each is 19,683 combinations — a few minutes of compute, not
a research project.

It was skipped because it would **overstate** the ranges rather than
refine them: the corners of that grid combine settings nobody would
defend together (`HEALTHY_SPREAD` at its lowest *and*
`MIN_SATURATION_POPULATION` at its highest), so the resulting spans
would describe configurations no one is proposing. The one-at-a-time
spans are a lower bound on the true uncertainty, and they are already
wide enough to make the point.

**If it were run, the useful output would be** the fraction of
combinations in which each *pairwise* ordering holds — "Winogrande above
GPQA Diamond in 97% of settings" is a defensible claim in a way that
"rank 1" is not.
