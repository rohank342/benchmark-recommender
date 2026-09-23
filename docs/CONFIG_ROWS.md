# Rows versus models

**Investigation only. No scoring change, and no second forward-test seal.**
All figures measured 2026-09-23 with `python probes/config_rows.py`
unless another command is named.

The forward-test amendment (`FORWARD_TEST.md`, Amendment 1) was
committed **before any number in this document was computed**, so the
designation of the corrected seal as primary could not be fitted to
these results.

---

## Corrections to last session's figures, first

Three numbers from the previous session's version of this probe do not
survive re-measurement, and two of them were quoted in `CLAUDE.md` and
`FINDINGS.md`. They were wrong for two compounding reasons, both in the
probe rather than in the catalog.

**Cause 1 — the probe matched CSV files by row count.** It searched
`EPOCH_DIR.glob("*.csv")` (unordered) for any file with a column holding
as many numeric values as the loaded score set, then grouped *that*
file. For Aider polyglot two different columns match at 77, and for
OSWorld and ARC the loader drops rows with an empty score so no file
matched at all. It is now keyed on the catalog's `epoch_source_file`.

**Cause 2 — blank model names were merged into a single model.** 188
rows across 10 Epoch benchmarks carry an empty `Model version`.
Collapsing them all into one group removed dozens of real rows from the
top band. They are now kept distinct.

| figure | last session | re-measured | status |
|---|---:|---:|---|
| GSM8K saturation, deduplicated | 0.632 | **0.289–0.292** | **wrong by ~0.34** |
| OSWorld on model counts | "falls below the 30 minimum" | **46 groups — stays measurable** | **wrong** |
| Aider polyglot, deduplicated | 0.350 | **0.556** (unchanged) | **wrong — wrong file** |
| benchmarks falling under every rule | 2 | **0** | wrong |
| Terminal Bench rows / models | 204 / 60 | 204 / 61 | holds |
| Epoch exports inflated | 9 of 20 | 13 of 20 | understated |

**The direction claim has now been wrong twice in this probe**, in
opposite ways: first asserted as "uniformly up" before counting, then
counted on a broken grouping. It is 8 up / 0 down / 8 rule-dependent,
below.

The amendment's cited case — Terminal Bench, 204 rows from ~60 models —
is the one figure that survived unchanged, which is why it was the one
quoted there.

---

## (a) Rows versus distinct models, every source

| source | benchmarks | inflated | worst case |
|---|---:|---:|---|
| Epoch AI | 20 | **13** | Terminal Bench 204 rows / 61 models (3.34x) |
| HF Open LLM v2 | 3 | **3** | 4,575 / 4,496 (1.02x) |
| HF Open LLM v1 | 1 | **1** | 7,170 / 6,812 (1.05x) |
| EvalPlus | 1 | 0 | one row per model |

**The two families are different in kind, not just in size.**

**Epoch** publishes one row per *configuration*: `Agent` (the scaffold
driving the model), `Edit format`, `Shots`, `Scaffold`, `Harness`. The
inflation is large and the configurations are not comparable with each
other — Terminal Bench's top 20% is 41 rows from **14** distinct models,
one contributing 10 of them, while the reading's own explanation string
says "the top 20% of 204 frontier models".

**HF** publishes one row per *precision*, and the cause is confirmed
rather than inferred: `Precision` differs in **355 of 355** v1 duplicate
groups and **79 of 79** v2 groups, usually with an identical `Model sha`
(`_load_leaderboard_frame`, live, 2026-09-23). The inflation is small
(1.02–1.05x) because only ~1–5% of models were submitted twice.

## (a2) 188 rows carry no model at all

| benchmark | blank | rows | share |
|---|---:|---:|---:|
| **OSWorld** | **37** | 57 | **65%** |
| GSM8K | 65 | 235 | 28% |
| HellaSwag | 22 | 135 | 16% |
| FrontierCode | 5 | 35 | 14% |
| MMLU | 32 | 249 | 13% |
| ARC, Aider polyglot, Winogrande | 8, 5, 8 | | 6% |
| BIG-Bench Hard, Terminal Bench | 4, 2 | | 4%, 1% |

**This is worse than a counting problem, and OSWorld shows why.** Its
blank rows are agent-only submissions — `agi-0 (50 steps)`,
`UI-TARS-2-2509 (100 steps)`, `DeepMiner-Mano-72B (100 steps)` — where
the agent *is* the system and Epoch attributes no model. 65% of
OSWorld's population is like this.

**No collapsing rule fixes that.** A saturation reading over OSWorld is
measuring agent systems, and calling the result "the top 20% of 57
frontier models" is wrong in the noun, not in the arithmetic.

---

## (b) What each source says about its own repeats

Cited, not inferred from the data.

### HF Open LLM Leaderboard — no canonical row, by design

> "Models may appear multiple times due to submissions under different
> commits or precision settings, like `float16` and `4bit`. You can check
> this by clicking on the `Precision` button under 'column visibility'…
> *Duplicates with identical precision and commit should be reported.*"
>
> — [huggingface.co/docs/leaderboards/open_llm_leaderboard/faq](https://huggingface.co/docs/leaderboards/open_llm_leaderboard/faq)

Different precisions are **intended entries**, each a legitimate result;
only identical-precision duplicates are errors. The leaderboard offers a
precision *filter*, not a designated default. **So HF documents the
cause and explicitly declines to name a headline row.**

### Epoch AI — two conventions, neither covering this case

**Repeated runs under identical conditions → the mean.**

> "For Epoch AI-administered benchmarks, we run most models multiple
> times on each benchmark (for most models, 16 times on GPQA Diamond and
> Mock AIME 2024-2025, 8 times on MATH Level 5)… In our main plot
> visualization, for each model and benchmark we show a confidence
> interval of plus and minus one standard error around the 'true' mean
> evaluation score."
>
> — [epoch.ai/benchmarks/about](https://epoch.ai/benchmarks/about)

**Variation between graders → the best.** This one is in the export
itself: `benchmark_metadata.csv` sets `score_column` to **"Best score
(across scorers)"** for GPQA diamond, MATH level 5, SWE-Bench verified,
SimpleQA Verified and MirrorCode, and those files carry both
`mean_score` and that column. Epoch has already collapsed grader
variation before this repo sees it, and it collapsed it to the best.

**Variation between agents, edit formats or shot counts → nothing.**
Epoch publishes one row per configuration and states no rule.
`epoch.ai/benchmarks/use-this-data` documents access and licensing only.
**This is the case that causes the inflation, and it is the case with no
documented convention.**

### EvalPlus — greedy pass@1, one row per model

No duplicates in the committed export, so no rule is needed. (The same
convention D5 adopted for HumanEval on the model side.)

---

## (c) Options, and what each asserts

| | rule | asserts | invents? |
|---|---|---|---|
| **(i)** | the source's own convention | — | **partly available only** |
| **(ii)** | best per model | a model's capability is its best demonstrated result; a weak scaffold measures the scaffold | **yes** — for agents/shots/precision |
| **(iii)** | median per model | a model's score is its typical configuration | **yes**, and more heavily |
| **(iv)** | canonical config per benchmark | the benchmark designates a reference setup | **no** — but **no benchmark here does** |
| **(v)** | keep rows, report the population honestly | nothing | **no** |
| **(vi)** | exclude unattributed rows | a score with no model is not a model's score | **no** |

**Option (i) is only half available, and that is the finding.** Epoch's
documented conventions cover graders (best — already applied upstream)
and repeated identical runs (mean — not the case here). Neither covers
agents, edit formats or shot counts. HF documents the cause and
deliberately designates nothing. So for the inflation that actually
matters, **there is no source convention to follow.**

**Option (iv) is unavailable for a different reason.** No benchmark in
the catalog names a reference agent, edit format or shot count — the
same finding D5 reached for Aider polyglot and Terminal Bench on the
model side. It would become available if a benchmark published one.

**Option (v) deserves more weight than it looks.** It invents nothing.
It requires only that the population be *named* accurately —
"model-configuration pairs", not "frontier models" — and that anything
comparing two benchmarks check that both are counted the same way. It
does not fix the top-band contamination.

**Option (vi) is orthogonal and can be combined with any of the others.**
Dropping the 188 unattributed rows asserts only that a row with no model
is not a model's score. For OSWorld it removes 65% of the population,
which is the honest consequence rather than an argument against it.

---

## (d) Impact of each rule, all 28 benchmarks

Saturation, per benchmark, for every benchmark with something to
collapse:

| benchmark | rows | models | as-is | best | worst | median | mean |
|---|---:|---:|---:|---:|---:|---:|---:|
| MMLU | 249 | 168 | 0.529 | 0.578 | 0.573 | 0.577 | 0.577 |
| MMLU-Pro | 4575 | 4496 | 0.158 | 0.158 | 0.158 | 0.158 | 0.158 |
| SWE-Bench Verified | 35 | 33 | 0.760 | 0.760 | 0.748 | 0.756 | 0.756 |
| HellaSwag | 135 | 98 | 0.483 | 0.486 | 0.469 | 0.474 | 0.474 |
| BIG-Bench Hard | 92 | 54 | 0.247 | 0.275 | 0.254 | 0.255 | 0.255 |
| TruthfulQA | 7170 | 6812 | 0.375 | 0.380 | 0.379 | 0.379 | 0.379 |
| **ARC** | 142 | 85 | **0.274** | **0.461** | 0.294 | 0.294 | 0.294 |
| Aider polyglot | 77 | 76 | 0.556 | 0.556 | 0.556 | 0.556 | 0.556 |
| **Terminal Bench** | 204 | 61 | **0.314** | **0.356** | **0.267** | 0.347 | 0.339 |
| **Winogrande** | 145 | 88 | **0.291** | **0.476** | 0.452 | 0.475 | 0.475 |
| GSM8K | 235 | 158 | 0.268 | 0.292 | 0.289 | 0.289 | 0.289 |
| MuSR | 4575 | 4496 | 0.055 | 0.055 | 0.055 | 0.055 | 0.055 |
| IFEval | 4575 | 4496 | 0.300 | 0.303 | 0.300 | 0.300 | 0.300 |
| **HLE** | 51 | 46 | **0.241** | **0.354** | 0.354 | 0.354 | 0.354 |
| OSWorld | 57 | 46 | 0.200 | 0.205 | 0.197 | 0.203 | 0.202 |
| The Agent Company | 16 | 14 | n/a | n/a | n/a | n/a | n/a |
| **TriviaQA** | 115 | 39 | **0.786** | **0.870** | 0.809 | 0.824 | 0.824 |

**Direction, counted rather than asserted: 8 rise under every rule, 0
fall under every rule, 8 depend on the rule.** The rule-dependent ones
matter most — Terminal Bench spans 0.267 to 0.356 depending only on
whether you keep a model's best or worst agent.

**Catalog-level effect:**

| rule | rank moves (of 28) | **tier changes** | mean health |
|---|---:|---:|---:|
| as-is | — | — | 49.2 |
| best | 7 | **0** | 47.8 |
| worst | 7 | **0** | 48.6 |
| median | 8 | **0** | 48.3 |
| mean | 8 | **0** | 48.3 |

**No benchmark changes evidence tier under any rule**, and no benchmark
falls below `MIN_SATURATION_POPULATION` on distinct-model counts. Both
are corrections to last session's claims. The change is real but modest:
a quarter of the catalog reorders and mean health falls about a point.

---

## (e) The population plateau, rechecked on model counts

| counted by | plateau (thresholds with no change to the measurable set) |
|---|---|
| rows | **17–35** |
| **models** | **15–33** |

The current 30 remains inside the plateau either way, but the headroom
above it shrinks from 5 to **3**.

**The watch list changes.** Margins above the 30-model minimum:

| benchmark | margin (rows) | **margin (models)** |
|---|---:|---:|
| **SWE-Bench Verified** | +5 | **+3** |
| FrontierCode | +5 | +5 |
| GSO-Bench | +8 | +8 |
| **TriviaQA** | +85 | **+9** |
| HLE | +21 | +16 |
| OSWorld | +27 | +16 |

**TriviaQA is the new entry**: 115 rows looked far clear of the line,
but 39 distinct models puts it fourth-closest. **OSWorld moves the
opposite way** to last session's claim — 46 groups, comfortably
measurable, not below the minimum.

---

## (f) Cross-source reproducibility: rows or models?

`cross_source._index_by_model` groups by `match_key` and **takes the
mean** of a model's rows:

```python
grouped.setdefault(key, []).append(score)
return {key: statistics.mean(values) for key, values in grouped.items()}
```

Two consequences.

**Overlap counts are not inflated.** The dict holds one entry per model
whatever the rule, so a duplicated model cannot be counted twice. All
eight measurable pairs draw on a set containing duplicate rows, and none
of their overlaps changes.

**But the reproducibility factor silently averages a model's
configurations** — exactly what D5 banned one layer down. It also drops
every blank-named row, because `if key:` skips them.

Scatter under each rule:

| benchmark | overlap | mean *(current)* | best | worst | median |
|---|---:|---:|---:|---:|---:|
| MMLU | 48 | 0.0086 | 0.0064 | 0.0105 | 0.0084 |
| GPQA Diamond | 29 | 0.0805 | 0.0805 | 0.0811 | 0.0805 |
| HellaSwag | 36 | 0.0180 | 0.0095 | 0.0167 | 0.0093 |
| BIG-Bench Hard | 25 | 0.0432 | 0.0598 | 0.0300 | 0.0559 |
| ARC | 40 | 0.0304 | 0.0452 | 0.0332 | 0.0298 |
| Winogrande | 39 | 0.0207 | 0.0164 | 0.0215 | 0.0181 |
| GSM8K | 36 | 0.0693 | 0.0694 | 0.0684 | 0.0682 |
| MATH Level 5 | 23 | 0.0253 | 0.0245 | 0.0245 | 0.0253 |

**`HEALTHY_SPREAD` survives.** It is derived as 3 × the *maximum*
scatter, and the maximum is GPQA Diamond's 0.0805 under every rule. So
the constant is unchanged at 0.24 even though several readings feeding
it move. **This is the one place in this investigation where the defect
does not propagate**, and it is worth saying because the default
assumption would be that it does.

---

## (g) The model side, beyond D5

D5 handled several entries under one label from one source. Two further
patterns, both measured:

**One measurement replicated across several Hub repos.** 14 `match_key`s
are shared by 43 Hub repos — quantized and format variants
(`-AWQ`, `-GGUF`, `-MLX-4bit`, `-FP8`) that collapse onto one key and
each inherit the same external score. On current data **8 of 81 scored
models** share a key, and among *ranked* models only **2 of 24** do:
`zai-org/GLM-4.5-Air` and `zai-org/GLM-4.5-Air-FP8`, with identical
composite scores of 0.0058.

Mechanism real, impact small — one duplicated pair in the visible
ranking. Recorded rather than fixed, per the rule about measuring impact
before ranking a finding. The honest treatment is probably the same as
D5's: show both, weight one, and say which.

**Cross-source repeats: zero.** No model/benchmark pair in the dataset
is cited by two different sources, confirming the existing finding that
sources cover disjoint benchmarks. D5's same-source rule therefore
covers every repeat that exists.

---

## What this document does not do

It implements nothing and picks nothing. The rule is the owner's
decision. Once chosen, the second forward-test seal is created under it
and designated primary, per Amendment 1 — which was committed before any
of the above was computed.

**If the decision is deferred, option (v) and option (vi) are still
worth taking on their own**, because neither invents a rule: name the
population accurately in the UI and in every explanation string, and
stop counting rows that carry no model as though they were models.
