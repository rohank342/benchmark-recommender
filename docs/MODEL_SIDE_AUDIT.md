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
