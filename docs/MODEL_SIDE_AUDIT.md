# Model-side audit

Analysis only, 2026-09-22. No fixes. The benchmark side has found four
bug classes; the model side was described in the brief as "downstream,
weaker" and had never been audited for any of them.

**Result: not clean. Three findings, one of them introduced today by a
benchmark-side fix that did not propagate.** Ranked by severity.

---

## 1. Tiering does not reach model scoring — **introduced today**

`scoring.py` weights each model result by `trust.health`. Evidence tiers
were added to the benchmark side this session precisely because a health
score resting on one factor is not comparable to one resting on three —
and **the model side takes the raw number anyway.**

So a model's MirrorCode result is weighted **95.1** (thin tier, score
computed from a release date, 8 scored models) while its Winogrande
result is weighted **59.0** (full tier, two measured factors, 145
models). The model ranking now leans hardest on the benchmarks with the
least evidence behind them.

This is the same inversion the tiering fixed one layer up, still live one
layer down.

**To fix:** either exclude thin-tier benchmarks from model weighting, or
weight within tier and combine tiers explicitly. Both are decisions about
what a model score means when its benchmarks are unequally evidenced, and
neither is a one-line change. **Severity: high** — it is a live
regression, and it silently inverts the thing the benchmark side just
corrected.

---

## 2. Disagreement between sources costs nothing — **bug class 1, mirrored**

The benchmark side measures cross-source scatter and scores
reproducibility from it. The model side does not measure agreement at
all. `_benchmark_weighted_mean` averages the points; nothing in
`scoring.py` computes a variance, a spread, or a disagreement penalty —
confirmed by grep: no `stdev`, no `variance`, no mention of disagreement.

Consequently:

| model | sources | trust |
|---|---|---|
| A | two sources reporting 65 and 65 | **0.798** |
| B | two sources reporting 45 and 85 | **0.798** |

**B's sources flatly contradict each other and it scores identically to
A.** Worse, the mean silently splits the difference at 65, so the output
looks like a consensus that does not exist.

This is the same shape as the benchmark-side bug — *being checked and
failing costs nothing* is the mirror of *being uncheckable pays* — and
the machinery to fix it already exists in `cross_source.py`, which
already splits offset from scatter for benchmarks.

**To fix:** compute the spread of a model's external scores and either
penalise it or report it, reusing `cross_source`'s offset/scatter split.
**Severity: high.** It is the exact failure the project has now corrected
twice elsewhere.

---

## 3. `raw_benchmark_score` holds several incomparable quantities — **bug class 3**

`_benchmark_weighted_mean` averages normalized results **across
different benchmarks**: a HumanEval pass@1, an MMLU accuracy, an
Artificial Analysis coding index. These are not the same quantity, and
averaging them produces a number that is not a score on anything.

This is the `contamination_effect` problem — one field holding two
things that cannot be compared — one level up, and CLAUDE.md §3 now
names that as an evidence-standard violation in its own right.

It is partly mitigated: the UI filters to a task category first, so the
benchmarks being averaged are usually related. But nothing enforces it,
and the model tab's composite is computed across whatever a model
happens to have been scored on.

**To fix:** either compute per-category scores and never pool them, or
record a basis saying what the composite is a composite *of*.
**Severity: medium** — real, long-standing, and mitigated in practice by
the category filter.

---

## 4. Unquantified flags at full severity — **bug class 2: NOT PRESENT**

The analogous case is an unknown result date. `_recency_factor` returns
**0.5** for unknown age, with the comment *"unknown isn't necessarily
old"* — a middle value, not the worst case.

That is the treatment the benchmark side eventually adopted for
contamination after getting it wrong, and the model side had it right
from the start. **Clean.**

---

## 5. Top-k / population artifacts — **bug class 4: NOT PRESENT as written**

No top-k over models exists in `scoring.py`; models are scored
individually, not ranked within a sampled band.

**But the population problem has a model-side analogue that is not
handled:** external scores are pooled across sources covering different
model populations (Artificial Analysis, Epoch, Hub model cards) with no
record of which population a number came from. The benchmark side now
carries `population` on every reading; the model side carries `source`
but never uses it to decide comparability. **Severity: low-medium**, and
it becomes finding 2's problem if disagreement is ever measured.

---

## 6. Did the score split break model scoring?

**No, and it was updated deliberately.** `_weighted_point` takes
`trust.health`, with a comment recording why relevance must not be used:
the task match is already applied when the category is chosen, so
weighting by relevance would apply the same judgement twice.

`UNKNOWN_BENCHMARK_TRUST` was re-checked at the same time and left at
45.0 on measured grounds (old combined median 41.5, health median 43.5).

**Clean — but see finding 1**, which is the part of the split's
consequences that did not propagate.

---

## 7. VRAM numbers and their basis

**Partly clean.** `hardware_filter.py` carries an explicit
`kv_cache_estimated` flag, `estimate_vram` returns `(gigabytes,
estimated)`, and the module header says outright that the numbers are
derived rather than measured.

**What is missing is the presentation.** The UI surfaces
`vram_total_gb` and `weights_gb` as plain numbers; the `estimated` flag
is computed and not shown. A reader sees a VRAM figure with no
indication that it was derived from parameter counts and a KV-cache
model rather than measured on hardware.

This is the same class as the benchmark side's `basis` display, which is
now shown per factor. **Severity: low**, and the fix is a UI change
rather than a modelling one — the flag already exists.

---

## Summary

| # | finding | class | severity |
|---|---|---|---|
| 1 | Tiering does not reach model weighting | new regression | **high** |
| 2 | Source disagreement costs nothing | uncheckability, mirrored | **high** |
| 3 | `raw_benchmark_score` pools incomparable quantities | one field, two quantities | medium |
| 5 | External sources pooled across populations | population | low-medium |
| 7 | VRAM `estimated` flag computed but never shown | basis display | low |
| 4 | Unknown age handling | — | **clean** |
| 6 | Score split consumption | — | **clean** |

Findings 1 and 2 are the same bug class the benchmark side has now fixed
twice. That the model side has it too, undetected until it was looked
for, is the argument for auditing it rather than assuming "downstream,
weaker" means "lower stakes".

---
---

# Options and measured impact — 2026-09-22

**Correction to this document's own severity ranking, first.** Findings 1
and 2 were ranked **high** on the strength of the mechanism. Measured
against the 215 models actually in `data/models_raw.json`, both are
**real in the code and close to inert in the data.** The ranking above is
wrong and is superseded by the table at the end.

## Finding 1 — tiering does not reach model weighting

### What the data says

| | |
|---|---|
| models scored | 81 of 215 |
| benchmark citations across them | 187 |
| citations of **FULL**-tier benchmarks | **0** |
| citations of **THIN**-tier benchmarks | **0** |
| citations of PARTIAL-tier benchmarks | 56 |
| citations of **unrecognised** benchmarks | **131 (70%)** |
| models with *no* recognised benchmark at all | **48 of 81 (59%)** |

**No model result cites a thin-tier benchmark, so the inversion I
described — MirrorCode outweighing Winogrande — does not occur once in
the current data.** The mechanism is genuinely wrong; the dataset does
not exercise it. Calling it "a live bug in shipped behaviour" overstated
it, and that overstatement set this session's priority order.

The reason is structural rather than lucky: the full-tier benchmarks are
the old HF v1/v2 set (Winogrande, BBH, ARC, GSM8K, MATH, MMLU, HellaSwag,
GPQA) and the catalogued models are mostly recent code models, whose
cards and Artificial Analysis entries cite coding benchmarks instead.
The two halves of the project barely overlap.

### The options, with measured impact

| option | invents a parameter? | models that move |
|---|---|---|
| **(i)** cap THIN weight at the max weight any PARTIAL benchmark gets | **no** — derived from the catalog | **0** |
| **(ii)** exclude THIN from weighting, show results beside the score | **no** | **0** |
| **(iii)** tier the model ranking itself | **no** | **unusable** |
| **(iv)** recognise more benchmarks, or give unrecognised results a basis | no | see below |

**(i) asserts** that a thin-evidence benchmark may still inform a model
score but must never carry more weight than a better-evidenced one.
Order-preserving, discards nothing. Zero effect today; it is a guard
against a case that will arrive when MirrorCode or LiveCodeBench start
appearing in model cards.

**(ii) asserts** that a score computed from a release date should not
weight anything, and belongs beside the number as unweighted evidence.
Stronger than (i) and also zero-impact today.

**(iii) is unusable as written.** It mirrors the benchmark side exactly —
and **0 of 81 scored models have any full-tier evidence**, so every model
would land in the same bottom tier. A tiering that puts everything in one
tier conveys nothing. That is a finding about the catalog's coverage, not
about the option: *the model side and the benchmark side are evaluated on
almost disjoint sets of benchmarks.*

**(iv) is where the actual problem is.** 70% of citations are
unrecognised benchmarks receiving a flat `UNKNOWN_BENCHMARK_TRUST = 45.0`
— higher than 18 of the 26 catalogued benchmarks' health scores — and 59%
of scored models rest on nothing else. **Whatever is decided about
tiering, the dominant input to model scoring today is a constant applied
to benchmarks nobody has assessed.** The largest citation is
`artificial_analysis_coding_index` (52), a composite index rather than a
benchmark, which cannot be assessed by this catalog at all.

### Plainly

**No option here both invents nothing and preserves usefulness, because
none of them changes anything.** (i) and (ii) are cheap, correct, and
currently cosmetic — worth doing as guards, not as fixes. (iii) cannot
be used. The useful work is (iv), which is a coverage problem, not a
weighting one.

---

## Finding 2 — source disagreement costs nothing

### What the data says

| | |
|---|---|
| scored models with 2+ sources | **6 of 81 (7%)** |
| model/benchmark pairs where two **different sources** report the same benchmark | **0** |

**CORRECTED 2026-09-22 (second pass).** An earlier version of this
section reported "1 pair, spread 0.022 (MiniMax-M2.7 on Terminal
Bench)". That was a miscount: those were two `epoch_ai` entries, not two
sources. **There is no cross-source disagreement in the dataset at all**,
so the finding is even lower-impact than first measured.

**What the miscount uncovered is larger.** The same source routinely
reports the same benchmark label several times — different pass@k
values, different languages, different runs — and every one of them is
averaged into the model's score:

| model | label | entries | range |
|---|---|---:|---|
| `bigcode/gpt_bigcode-santacoder` | MultiPL HumanEval (Python) | **20** | 0.15 – 0.77 |
| `bigscience/bloomz-560m` | HumanEval | 3 | 0.022 – 0.090 |
| `Qwen/Qwen2.5-Coder-32B-Instruct` | Aider polyglot | 2 | 0.080 – 0.164 |

A five-fold range under one label, silently averaged, is finding 3
(`raw_benchmark_score` pooling incomparable quantities) in its most
concrete form.

**There is exactly one instance of measurable disagreement in the entire
dataset, and it is 2.2 points.** The 45-vs-85 example in the audit above
was constructed to show the mechanism, not drawn from data.

The reason is again structural: sources cover **disjoint** benchmarks.
Artificial Analysis reports its own indices, Epoch reports its own set,
Hub cards report whatever the lab chose. Two sources rarely report the
same benchmark for the same model, so there is usually nothing to
disagree about.

**The bug is real and low-impact.** Saying so is the point of measuring
before fixing.

### The options

| option | invents a parameter? | effect today |
|---|---|---|
| **(i)** status quo | no | — |
| **(ii)** surface spread in the UI, no scoring change | no | shows 1 model a 0.022 spread |
| **(iii)** discount report-trust by measured spread, reusing `cross_source`'s offset/scatter split | **no** — `SCATTER_TOLERANCE` already exists | 1 model, negligibly |
| **(iv)** tier by agreement | no | 1 model changes tier |

**(iii) reuses rather than invents**, which matters: `cross_source.py`
already splits a systematic offset from irreproducible scatter and
already has `SCATTER_TOLERANCE = 0.08`. Any second mechanism for the same
idea would be a duplicate with its own constant.

**(iv) follows directly from the two-trusts design already in the
brief.** CLAUDE.md §4 says ranking is tiered before scores compare —
confirmed provenance above unconfirmed, corroborated above self-reported
— "because a multiplier can't express *an unverified number is not
evidence*". **Corroborated-and-agreeing above corroborated-and-
disagreeing is the same sentence with one more rung**, and the tier
machinery is already there. It is the option that adds least that is new.

---

## Finding 3 — `raw_benchmark_score` holds incomparable quantities

**This needs a design change, not a basis field, so nothing was built.**

A basis field works for `item_error_rate` and `contamination_effect`
because those record *one* claim whose kind varies. `raw_benchmark_score`
is different: it is a *mean over several claims of different kinds*, so
there is no single basis to record. Labelling it "mixed" would document
the problem without fixing it.

What the data shows the field currently averages, per model: an
Artificial Analysis coding index (0–1 rescaled from a 0–82 composite), a
HumanEval pass@1, a Terminal Bench success rate, and `MultiPL HumanEval
(Python)`. Those are not the same measurement and their mean is not a
score on anything.

**The design change would be:** compute and store a score *per benchmark
category*, never pooling across categories, and have the UI show the
category matching the user's task rather than a composite. Consumers
needing one number — the ranking, `composite_score` — would need to say
which category they are ranking within, which is the same move the
benchmark side made when it split health from relevance.

**Estimated scope:** `_DataPoint`, `_benchmark_weighted_mean`,
`ScoredModel`, the ranking, and the model tab. Not a field addition.
Described here rather than built, per instruction.

---

## Superseding severity table

| # | finding | mechanism | impact on current data | revised severity |
|---|---|---|---|---|
| 1 | tiering absent from model weighting | wrong | **zero citations affected** | **low** (guard) |
| 2 | disagreement costs nothing | wrong | **1 pair, 0.022** | **low** |
| 3 | `raw_benchmark_score` pools kinds | wrong | every scored model | **medium-high** |
| **new** | **70% of model evidence is unrecognised benchmarks at a flat 45.0** | — | **59% of models rest on nothing else** | **high** |

The audit's original ranking put mechanism ahead of impact. Measuring
first would have caught that, and it is the same lesson the benchmark
side learned when an unquantified flag turned out to cost more than a
measured one.

---
---

# The unknown-benchmark default, and what models actually cite — 2026-09-22

## `UNKNOWN_BENCHMARK_TRUST` — options, no pick

### Measured first

| | |
|---|---|
| models whose rank depends on it | up to **33 of 81** |
| catalogued benchmarks scoring **below** 45.0 | **8 of 28** |
| health distribution now | min 15.5, median 54.9, max 95.1 |

| value | models changing rank |
|---:|---:|
| 0 | 33 |
| 20 | 17 |
| 30 | 9 |
| **45 (current)** | — |
| 60 | 10 |
| 100 | 16 |

**A correction to my own earlier claim.** I reported that 45.0 "sits
above 18 of 26 measured health scores". It sits above **8 of 28**. The
health distribution moved up when unmeasurable factors stopped
contributing and `HEALTHY_SPREAD` was derived; I quoted a figure from
before those changes. **The default is now slightly below the median,
not generous** — the fifth-instance framing was overstated, though the
structural point stands: nothing about it is derived.

### Was it derived?

**No.** It entered in the pivot commit `e965175` with the comment
*"Middling on purpose: an unknown benchmark is not evidence of a bad
one, but it can't be trusted like a benchmark that has been assessed"* —
and a `TODO(you): shrink this as the catalog grows`. Same commit and
same status as `HEALTHY_SPREAD`, which was also chosen and has since
been derived.

### The options

| option | invents a parameter? | impact |
|---|---|---|
| **(i)** status quo, 45.0 | it already is one | — |
| **(ii)** re-derive from the current health distribution | **yes** — which statistic? | median 54.9 moves 10 models; mean 51.3 moves ~8 |
| **(iii)** own tier below THIN, excluded from weighting | **no** | **47 of 81 models lose all weighted evidence** |
| **(iv)** treat composites as a distinct kind, then re-ask | no | see below |

**(i) asserts** that an unassessed benchmark is worth about as much as a
median assessed one. Nothing supports that; it is a placeholder that
has outlived two scale changes.

**(ii) asserts** that the typical assessed benchmark is the right stand-in
for an unassessed one. It invents a parameter in the same way the old
value did — "which statistic of the distribution?" is exactly the
quantile choice that `HEALTHY_SPREAD`'s derivation had to make. It is
also unstable by construction: the value would move every time a
benchmark is added, which is the property the `HEALTHY_SPREAD` note
explicitly warned against.

**(iii) asserts** that a benchmark nobody has assessed cannot weight a
model's score, exactly as a thin-tier one cannot. It invents nothing and
is consistent with D1. **Its cost is the finding:**

> **47 of 81 scored models (58%) would have NO weighted evidence at
> all.** Counting the 134 models that have no score today, **181 of 215
> (84%) would have no weighted score.**

**What the UI would show for such a model:** its results, its sources,
and "no weighted evidence — every benchmark this model reports on is
outside the catalog", with the unweighted numbers displayed beside it.
Under Reading B that is an honest page rather than an empty one. It also
makes the model tab's real state visible instead of hiding it behind a
default — **which is the argument for (iii) and the argument against it,
depending on whether the model tab is meant to rank or to inform.**

---

## What models cite: composites, aliases, and the tail

### The citation curve

| | citations | share |
|---|---:|---|
| catalogued benchmarks | 58 | **31%** |
| `artificial_analysis_coding_index` (a composite) | 52 | 28% |
| `MultiPL HumanEval (Python)` (one model's card, 20 variants) | 20 | 11% |
| long tail | 57 | 30% |

**57 of the 60 distinct unrecognised labels are cited exactly once**, and
**one model — `bigscience/bloomz-560m` — contributes 50 of them** by
listing its entire XCOPA / XStoryCloze / XNLI / XWinograd suite across
dozens of languages.

| to reach | additions needed |
|---|---|
| 50% of citations | **impossible** without cataloguing one model's multilingual suite |
| 33% | the 5 most-cited true benchmarks |
| 60% | every singleton label — 57 entries, each cited by one model |

**Citation-weighted coverage is the wrong metric.** Model-weighted
coverage — models with at least one catalogued citation — is **42%**, and
is what actually matters for whether a model's score rests on assessed
evidence.

### Composites — design only

`artificial_analysis_coding_index` is 28% of all citations and is **not a
benchmark**. It is a published aggregate over several benchmarks, scaled
0–82 in the source and rescaled here.

**It double-counts.** Its components overlap benchmarks this catalog
already weighs separately — Artificial Analysis's coding index has
historically included LiveCodeBench and SciCode among others — so a model
carrying both the index and a component benchmark has that component
counted twice, once assessed and once inside an unassessed aggregate.

**Three ways to treat it, none implemented:**

1. **Decompose** — record the index's components and their weights, and
   attribute the score to them. Correct in principle; requires the
   provider to publish component weights, which change between index
   versions (v2 → v3 → v4 dropped and added several), so it is a moving
   target this repo would have to re-verify each release.
2. **Exclude** — composites carry no weight, like thin-tier benchmarks.
   Simple, consistent with D1 and (iii), and removes 28% of the model
   side's evidence at a stroke.
3. **Mark as a distinct kind** — a `composite` flag on the data point, so
   it is displayed, never weighted, and never double-counts. This is the
   basis-field pattern applied to a kind rather than a value, and is the
   cheapest of the three.

**Recommended for the owner's decision: (3).** It invents nothing,
matches how every other "we cannot assess this" case has been handled,
and preserves the evidence for display.

### Alias check — one real match, three traps

| candidate | verdict | evidence |
|---|---|---|
| **`Winogrande XL (xl)` → Winogrande** | **MATCH** | "xl" is the standard Winogrande config name (the 40k-example training size); the benchmark is identical. Safe to alias. |
| `XWinograd (en/fr/jp/pt/ru/zh)` → Winogrande | **NOT A MATCH** | XWinograd is a *different* multilingual Winograd-schema set, not Winogrande. Merging would repeat the SimpleQA / SimpleQA Verified error in reverse. |
| `GSM8K (PAL)` → GSM8K | **NOT MERGED** | Same problems, but PAL is a different *evaluation protocol* (program-aided prompting) producing systematically different scores. Same trap as the raw-vs-rescaled column bug. |
| `MultiPL HumanEval (Python)` → HumanEval | **NOT MERGED** | MultiPL-E is a translation harness; its Python config is close to HumanEval but not identical, and the citing card reports 20 different values under the label. Merging would import that spread into HumanEval. |

**Only the Winogrande XL alias is safe**, and it is worth one line. The
other three are exactly the kind of match that looks free and is not.

---
---

# Repeated labels: measured, and the cause found — 2026-09-22

## Measurement

Command: a grouping of `benchmark_breakdown` by `(benchmark, source)`
over `data/models_raw.json`, run this session.

| | |
|---|---|
| model/label/source groups with 2+ entries | **15**, across 15 of 81 scored models |
| spread: min / median / max | 0.000 / 0.043 / **0.620** |
| groups exceeding the benchmark side's 0.08 scatter tolerance | **5** |

Largest groups:

| spread | entries | model | label | source |
|---:|---:|---|---|---|
| **0.620** | 20 | `bigcode/gpt_bigcode-santacoder` | MultiPL HumanEval (Python) | hub card |
| 0.084 | 2 | `Qwen/Qwen2.5-Coder-32B-Instruct` (×4 repo variants) | Aider polyglot | epoch |
| 0.074 | 2 | `MiniMaxAI/MiniMax-M2.1` | Terminal Bench | epoch |
| 0.068 | 3 | `bigscience/bloomz-560m` | HumanEval | hub card |

## Why the repeats exist — inspected, not guessed

**They are not disagreement. They are incomparable configurations
collapsed under one label**, which is the one-field-two-quantities bug
appearing a third time.

**Hub cards — different `metric_name` under one `dataset`.** The 20
santacoder entries are `pass@1`, `pass@10`, `pass@100` and `exact_match`
all labelled "MultiPL HumanEval (Python)":

```
{"dataset": "MultiPL HumanEval (Python)", "metric_name": "pass@1",   "metric_value": 0.18}
{"dataset": "MultiPL HumanEval (Python)", "metric_name": "pass@10",  "metric_value": 0.29}
{"dataset": "MultiPL HumanEval (Python)", "metric_name": "pass@100", "metric_value": 0.49}
```

`pass@100` exceeds `pass@1` by construction. Averaging them is not
reconciling a disagreement, it is adding different quantities.

**Epoch — a distinguishing column this repo drops.** Aider polyglot's
export carries an `Edit format` column:

| Percent correct | Edit format | Percent using correct edit format |
|---:|---|---:|
| 8.0 | `diff` | 71.6 |
| 16.4 | `whole` | 99.6 |

Same model, same date, two evaluation protocols, averaged to 12.2. This
is the same class as the `GSM8K (PAL)` alias declined last session:
same problems, different protocol, different score.

## Options — no pick

| option | asserts | invents? |
|---|---|---|
| **(i)** status quo | that a mean of pass@1 and pass@100 is a number | — |
| **(ii)** weight none when they disagree beyond 0.08 | that repeats are disagreement | nothing, but **the premise is wrong** — they are different metrics, and 0.08 is a tolerance for measurement noise, not for `pass@k` |
| **(iii)** pick one by a rule the data supports | that one configuration is canonical | **the metadata exists for both cases**: `metric_name` for hub cards, `Edit format` for Epoch. The rule would be "prefer the benchmark's canonical protocol" — `pass@1` for HumanEval-family, and the edit format the benchmark's own leaderboard reports |
| **(iv)** carry the configuration into the label | that `HumanEval (pass@1)` and `HumanEval (pass@100)` are different series | nothing; it is the largest change, and it is what the data actually says |

**(ii) is the option this session's investigation argues against**, and
that is worth stating since it was the obvious candidate before the
cause was known.

## What changed this session

**Disclosure only. No score moved.** Every repeated group now reports
its size, spread and values in `benchmark_breakdown["repeated"]`, and
the model table shows `⚠ mean of 20 entries spanning 0.62` next to the
averaged value. An averaged number can no longer look like a single
measurement.
