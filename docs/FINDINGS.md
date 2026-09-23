# Findings

*Written 2026-09-22. Every figure in this document was recomputed on that
date from the data committed in this repository. Each is footnoted with
the command that produces it; most come from `probes/findings.py`, which
exists so that a reader can check the numbers rather than trust them.*

---

## Scope, before anything else

This project scores **benchmarks**, not models: it asks whether a
measurement still separates the things it measures. The premise is that
a benchmark's popularity is not evidence that it still discriminates,
because labs optimize against well-known benchmarks and public test sets
leak into training corpora.

**What this project does not show, stated first:**

- **It does not show that its composite score ranks benchmarks better
  than sorting by release date.** Three tests have been run to a
  conclusion and none established that. One is reported below in which
  the single age-derived factor, alone, beats all four factors together
  on the metric the test was built around.
- **It does not establish a ranking of benchmarks.** Scores rest on
  unequal amounts of evidence, and a comparison between two benchmarks
  in different evidence tiers is not a claim this project makes.
- **It does not measure task relevance.** The `specificity` factor is
  an auditable judgement against a written rubric, scored for all 28
  benchmarks by Claude Code and reviewed by nobody else. [2]
- **Its coverage is partial and uneven.** Saturation is measured for 23
  of 28 benchmarks, cross-source reproducibility for 8, a contamination
  *rate* for 3, an item error rate for 4. [2]
- **Its forward-looking claim is untested.** The only live validation
  matures 2028-09-22.

What it does contain is a dated, sourced, per-benchmark evidence record,
and a set of failures that were found by looking at real output. Both are
below.

---

## 1. The thesis, as evidence about one benchmark

The founding case is HumanEval, stated as what the catalog holds about
it rather than as a rank. Re-measured 2026-09-22: [1]

| | |
|---|---|
| released | 2021-07-07, public and static since |
| measured saturation | **0.438**, over the top 20% of 125 code models submitted to EvalPlus |
| contamination rate | **0.13** — recorded from Riddell et al.'s reported 8–18% of items appearing in major open-weight pretraining corpora |
| contamination effect | **0.394** — scores fall 39.4% on EvoEval, basis recorded as **`uncontrolled`** |
| item error rate | **`None`** — meaning nobody has audited the answer keys |
| reproducibility | **unmeasurable**: only one source covers it |
| measurement health | **28.1**, resting on 2 of 3 factors (`partial` tier) |

Read that as a row of evidence, not a verdict. A benchmark everyone
quotes, whose leakage into training data has been measured, whose
contamination effect **cannot be cleanly separated from difficulty**
because EvoEval did not control for it, and whose answer key nobody has
checked. The `uncontrolled` basis is the point: 0.394 is a real published
number that does not mean what a naive reading of it means, and the field
says so rather than folding a correction the evidence does not contain.

**A superseded headline, recorded rather than deleted.** This project
used to open with **"HumanEval scores 30.6/100 while MirrorCode scores
76.3"** (the form preserved in `SCORE_SPLIT_PROPOSAL.md`). That
comparison is dead. The two are in different evidence tiers —
MirrorCode's score rests on a release date alone, with 8 scored models
and no measurable saturation [6] — so they are not ranked against each
other and the numbers were never comparable. The thesis never needed the
comparison.

Two details of its death are worth keeping. First, neither figure is
stable: the same two benchmarks read **28.1 and 95.1** today [1][6], and
the headline has been retold elsewhere with a third pair of numbers
again. A claim whose numbers drift between retellings was never resting
on those numbers. Second, the gap *widened* — so the comparison was not
dropped because it stopped being flattering. It was dropped because it
was never a comparison.

---

## 2. What the catalog establishes

28 benchmarks across 10 task categories. Every curated claim carries its
basis in `curation_notes` — either `RESEARCHED <date>` with a citation,
or a `CURATE(you)` marker naming what is missing. Coverage, re-measured: [2]

| measurement | benchmarks |
|---|---:|
| has any score source | 25 of 28 |
| **saturation measured** from a real score distribution | **23 of 28** |
| **cross-source agreement** (same models, two evaluators) | **8 of 28** |
| contamination *rate* known | 3 of 28 |
| contamination *effect* known | 2 of 28 |
| contamination flagged but never quantified | 13 of 28 |
| item error rate known | 4 of 28 |
| specificity rubric scored (by Claude Code only) | 28 of 28 |

Three distinctions in that table carry most of the project's weight:

**`None` is not zero.** `None` means nobody looked; an explicit `0.0`
means someone looked and found nothing. Tests enforce the distinction.
HumanEval's item error rate is `None`, and that is a finding about the
literature, not a neutral default.

**A bound is not an estimate.** `item_error_rate_basis` is either
`estimate` or `lower_bound`. SWE-Bench Verified's 0.164 is a floor from
an audit covering 27.6% of the set, so it is recorded as `lower_bound`.
Scoring is *identical* for both bases — charging a bound more harshly
would mean inventing a severity the evidence does not contain — and only
the wording changes.

**Every reading names its population.** Saturation over "the top 20% of
125 code models submitted to EvalPlus" and over "the top 20% of 4,575
open community models" answer different questions. The readings in the
catalog come from four populations [2] and are not comparable across
them. This is stated in the data, not in a caveat.

---

## 3. Every test that has been run

### 3.1 The HF retirement backtest — retired on power

In June 2024 Hugging Face retired six benchmarks from the Open LLM
Leaderboard and replaced them with six harder ones. All twelve are in the
catalog. Scored as of 2024-06-01, using only evidence that was public by
then, do the retired six rank below the replacements?

Headline result: **10 of 12 correct, separation lost by 26.9 points**,
with MATH Level 5 (kept) ranking below five retired benchmarks. [3][9]

That number is not the finding. The finding is what happens when the
test is scored pairwise and compared against a baseline: [3]

| | pairs | correct |
|---|---:|---:|
| the scorer | 30 | **30 (100%)** |
| sorting by release date | 30 | **30 (100%)** |

Six of the 36 retired-vs-kept pairs are void because they span evidence
tiers, and **all six involve MATH Level 5**, which has 29 models at the
cutoff and is therefore `thin`.

**Both are perfect, so the test cannot distinguish them — and never
will.** This is not a shortage of data. It is a property of these twelve
benchmarks: HF retired the older six and kept the newer six, so on every
valid pair the calendar and the scorer agree *by construction*. The six
pairs where they could have disagreed are exactly the six that are not
valid comparisons.

The test was therefore **retired on power, not on its result**. A test
that returns 100% and cannot fail is not evidence, for the same reason a
test returning 0% would not be.

> **Do not quote the 30/30.** The baseline it is supposed to beat scores
> identically, and the comparisons that would have separated them were
> excluded as invalid. Citing it as vindication would be the most
> misleading thing this project could say about itself.

### 3.2 The single-factor comparison — the sharpest negative result

Isolating each health factor at weight 1.0, against the trivial baseline
of sorting by release date and calling the newer half "kept": [9]

| ranked by | correct | separation gap |
|---|---:|---:|
| the full scorer (all factors) | 10/12 | **−26.9** |
| **freshness alone** (age decay) | **10/12** | **−6.3** |
| **release date alone** (no scoring at all) | **10/12** | — |
| discrimination alone (measured saturation) | 6/12 | −24.4 |
| reproducibility alone | 6/12 | −60.0 |

Freshness alone matches the full scorer on correctness and loses
separation by **a quarter as much**. Measured saturation alone gets 6 of
12, which is exactly chance. On this test, adding the three
non-age factors to the calendar proxy makes the margin worse.

**This comparison had not run for 28 commits.** `backtest.py --sweep`
raised `ZeroDivisionError` from commit `e247226` (which introduced
drop-and-renormalize) until it was fixed on 2026-09-22. Isolating a
factor sets the other weights to zero; when the surviving factor was one
the benchmark had dropped as unmeasurable, the renormalizer divided by a
zero total. Production weights are all non-zero, so no score was ever
wrong — but the single-factor analysis, and the release-date baseline
printed after it, silently stopped running. The crash was found by
running the command the project's own brief names as its headline
diagnostic. Two figures quoted in that brief ("separation lost by 0.6
points"; "four different single-weight changes each produce 12/12") did
not survive re-measurement: the gap is −26.9 and **no** weight setting in
the sweep reaches 12/12. [9]

### 3.2b What actually predicts the decision

Correlating each candidate signal against HF's retire/keep label across
the twelve, at the cutoff: [8]

| signal | r with "kept" |
|---|---:|
| **release date** (age) | **−0.793** |
| the composite health score | +0.502 |
| measured saturation | −0.198 (n=11) |

Age predicts the decision far better than the score built to predict it.
Measured saturation — the factor carrying the most weight — barely
predicts it at all, and `r(age, saturation) = +0.202` shows saturation is
not merely standing in for age either. On this set it adds little in
any direction.

*Corrections to this project's own record, both re-measured here:* the
brief states `r(age, saturation) = +0.01` and `r(saturation, label) =
+0.300`. They are **+0.202** and **−0.198**. The conclusion drawn from
them — that saturation adds almost nothing over age on these twelve — is
unchanged and, on the second figure, stronger than recorded.

### 3.3 Candidate 1 — pre-registered, run, failed

Pre-registered in `SECOND_TEST_PREREGISTRATION.md` and run on
2026-09-21: three weeks before OpenAI publicly abandoned SWE-Bench
Verified, did the scorer rank it below GPQA Diamond, which stayed in use?

It did not. Scored at the registered as-of date of 2026-02-01, the scorer
puts **SWE-Bench Verified above GPQA Diamond** — the same ordering the
calendar gives, and the wrong one. [4]

Re-measured today the margin is **+1.1 points**; the pre-registration
recorded **+16.6** under the definitions then in force. The direction,
which is the failure, is unchanged; the magnitude moved with three
definition changes since. That is why it is recomputed here rather than
quoted.

The test is additionally **void**: at that date SWE-Bench Verified is
`thin` and GPQA Diamond is `partial`, so the pair spans evidence tiers
and is not a comparison this project makes. [4]

Two separate defects surfaced while auditing it, both recorded below as
bug classes: the two benchmarks had 18 and 196 dated models, so the test
compared the top 56% of one against the top 5% of the other; and the
result flipped from FAIL to PASS at one point purely because SWE-Bench
Verified's discrimination became *unmeasurable* and dropped out of its
score. The pre-registration had already named that as evidence *against*.

### 3.4 The hindcast — descriptive only, and two of its rows were wrong

Pre-registered, run three times, and never a script: each run was done by
hand and its table pasted into the document. It is now reproducible. [13]

Result: **2 of 4 discordant pairs** — a coin flip on four data points. It
was declared descriptive before it was run, and four pairs cannot support
a conclusion in either direction, which is why the forward test fixes a
minimum of ten in advance.

**Making it runnable found a defect in the recorded table.** Two of its
five rows read saturation *at T* from Epoch (81 and 33 models) while
reading saturation *at the outcome* from the HF v2 leaderboard (4,575
models). The other three are v2 at both ends. That is the exact failure
the pre-registration was written to prevent — its own population section
reads *"v2 is the only source where every eligible benchmark shares one
model population at both dates"* — and it is §4.3's bug class appearing
inside the document that names it.

Under the registered v2-at-both-ends rule, **BIG-Bench Hard's change flips
sign** (−0.031 → +0.028) and **GPQA Diamond's decline halves** (−0.315 →
−0.168). [13] Those two rows carried the document's "the outcome
mean-reverted" reading, so that description is withdrawn: on the
registered population three of the five became *more* saturated over the
nine months.

**The pre-registered result is unchanged: still 2 of 4.** The primary
metric depends on the ordering of trust at T and on saturation at the
outcome, neither of which was contaminated — only the descriptive
columns. Stated plainly because the convenient move would be to present a
corrected defect as a corrected result, and it is not one.

### 3.5 ARC-AGI-1 — scoped and rejected

The most valuable missing case is an *old but unsaturated* benchmark,
where age and measurement health would predict opposite things. ARC-AGI-1
was scoped for this and rejected: almost all of the available models
postdate the window.

Re-derived 2026-09-23 [14]: the HF dataset `arcprize/arc_agi_v1_public_eval`
holds **75 model directories, of which 4 predate the 2024-06-01 as-of
date.** The saturation minimum is 30. ARC-AGI-1 at a 2024 as-of date
would therefore be `thin` tier — discrimination unmeasurable, score
resting on freshness alone — and a thin-tier benchmark cannot be compared
with the partial-tier comparators at all. That is precisely how
Candidate 1 died, and the test would reproduce it after paying for a
fetcher and a curation pass.

*This footnote needs the network* and so is the one figure here CI cannot
check; the probe lists every directory it could not date, and the count
would have to rise from 4 to 30 to change the recommendation.

---

## 4. Bug classes

Every one of these was found by looking at real output, not by planning.
They are grouped because each is a *class*: the instance is less useful
than the shape.

### 4.1 Being uncheckable used to pay

The recurring defect. A fallback, a default or a flag scored *better*
than the measurement it replaced, so gathering evidence lowered a score
and having none raised it. Five instances, all now fixed or guarded:

1. **Reproducibility fell back to an evaluator count** whose mean across
   the catalog (0.580) was *higher* than the measurement it stood in for
   (0.485). ARC scored 1.000 on reproducibility because its sources could
   not be compared at all. Fixed by dropping unmeasurable factors
   entirely — which created a worse bug, see §4.4.
2. **An unquantified contamination flag took the maximum penalty.** A
   flat 0.65 multiplier, identical to what a measured severity of 1.0
   produces. "Reported, nobody measured it" cost exactly as much as
   "measured to be maximally contaminated", so measuring bought nothing.
   Now it carries **no numeric penalty and is shown as a WARNING**. The
   cost of that fix is real and is stated: unmeasured-but-real
   contamination is now free, and SWE-Bench Verified is the live example
   — 13 of 28 benchmarks are flagged without a quantified rate. [1][2]
3. **Model-side source disagreement costs nothing**, so two sources that
   contradict each other score like two that agree.
4. **Evidence depth inverted the ranking twice** — once on the benchmark
   side (thin scores outranking thick) and once on the model side
   (thin-tier benchmarks carrying weight).
5. **`UNKNOWN_BENCHMARK_TRUST`**, a flat 45.0 applied to any benchmark
   the catalog had never assessed. It was chosen as "middling on purpose"
   in the pivot commit and never re-derived through two scale changes.
   It has since been removed from scoring: unknown benchmarks now form
   their own tier below `thin`, are excluded from weighting, and are
   shown as unweighted evidence.

   *A correction belonging to this entry.* An earlier report claimed 45.0
   "sits above 18 of 26 health scores". Re-measured after the scale
   moved, it sat above only **8 of 28**. The instance was real; the
   severity was overstated by a figure carried forward from a previous
   state. This is the reason for the standing rule that every number in
   a report must be re-measured in the session that reports it.

**The test to run against any new rule:** does having less evidence, or
failing a check, ever come out better than having more or passing? If the
answer needs thought, it is probably yes.

### 4.2 One field holding two incomparable quantities

`contamination_effect` held HumanEval's 0.394 — from EvoEval, difficulty
**not** controlled — beside GSM8K's 0.051, from GSM1k, which is
difficulty-matched. Both are real published numbers. The penalty formula
could not tell that they measured different things, and a field displaying
one decimal place implied they were the same kind of quantity.

**"Sourced" is necessary and not sufficient.** The question is whether two
values in one field can be compared with each other. The remedy is a
basis field (`contamination_effect_basis`, `item_error_rate_basis`), and
scoring stays identical across bases because discounting one would mean
inventing a correction.

One instance of this class remains **unfixed** and needs a design change
rather than a basis field: `raw_benchmark_score` averages a HumanEval
pass@1 with an Artificial Analysis coding index. A basis records one claim
whose *kind* varies; this is a mean over several kinds.

### 4.3 Population artifacts

Four distinct instances of the same root error — a number that describes
the measuring population, mistaken for a number that describes the
benchmark.

- **Top-k-of-n is not one statistic.** Saturation read the top 10 models,
  which is the top 30% of a 33-model population and the top 0.2% of a
  4,575-model one. Readings moved by up to 0.81 with no change to the
  benchmark. Fixed with a percentile; any "top k" over variable-sized
  groups is this bug.
- **Which population you measure changes the answer.** GPQA Diamond
  reads **0.664 saturated across 313 frontier models and 0.190 across
  4,575 open community models** — the same benchmark, the same day, a
  3.5x difference. [2] Picking the larger sample silently answered a
  different question. Population is now part of the reading, not a label
  beside it.

  *A correction belonging here.* This project's brief records this
  instance as "89% among frontier models, 59% among open-community
  ones". Those were the readings under the old top-10 definition;
  re-measured under the percentile band they are 66.4% and 19.0%. The
  finding is unchanged and the gap is in fact wider than recorded.
- **Comparing two benchmarks can mean comparing two populations.**
  Candidate 1 put SWE-Bench Verified (18 dated models) against GPQA
  Diamond (196) and compared the top 56% against the top 5%. Caught only
  by auditing a result that had already been reported.
- **An archived leaderboard freezes its readings.** Saturation still
  depends on whether anyone still submits to the leaderboard that scores
  a benchmark. The v1 leaderboard's six move by exactly zero because it
  is archived. **No fix proposed** — this one is open.
- **Configuration rows counted as models — the largest instance, and
  still live.** Found 2026-09-23 while fixing the model-side version of
  the same defect (§4.5). Epoch's per-benchmark exports carry a column
  separating several runs of the *same* model: `Agent` (the scaffold
  driving it) for Terminal Bench and OSWorld, `Edit format` for Aider
  polyglot, `Shots` for the older multiple-choice sets. Every row is read
  as one score, so a benchmark's "population" is model-configuration
  pairs. **9 of 20 committed Epoch exports hold more rows than distinct
  models** — Terminal Bench 204 rows from 60 models, OSWorld 58 from 10,
  GSM8K 235 from 94. [15]

  Two consequences. The top-20% band partly measures scaffold and
  shot-count variance rather than differences between models: Terminal
  Bench's top 20% is 41 rows drawn from **14** distinct models, one
  contributing 10 of them — while the reading's own explanation string
  says "the top 20% of 204 frontier models", which is not true of the
  data. And the 30-model minimum is applied to the wrong count: OSWorld
  clears it on 58 rows while having 10 models.

  Deduplicating to one row per model moves GSM8K 0.268 → 0.632 and drops
  OSWorld below the minimum entirely. [15] **Direction, counted rather
  than asserted:** of the 12 that stay measurable, 9 read *more*
  saturated under both dedup rules, 2 read *less* (SWE-Bench Verified,
  and Aider polyglot 0.556 → 0.350), and 1 depends on the rule. A first
  draft of that probe concluded "uniformly up" before counting — the
  §4.6 bug class about inventable directions, caught in this project's
  own output.

  **Not fixed.** It moves every score in the catalog, and the forward
  test's baseline was sealed under the current definition. No benchmark
  here names a reference agent or shot count, so picking one would be
  inventing a protocol — the thing §4.5's fix refused to do.

A near-miss in the same family, worth recording because it was caught by
probing rather than reading: MuSR's random baseline was recorded as 0.33
"because it has three options". Probing the dataset showed the
murder-mystery split is **binary** and object placement runs 2–5 options
per item; the true aggregate is 0.371. Assumed chance levels are a whole
class of this bug — check the items, not the description.

A related archive artifact: the archived v1 leaderboard marks `Flagged`
True for **every** row. It is a property of the archive, not a
per-model judgement, and filtering on it silently dropped all 7,260
models.

### 4.4 A fix can create a worse bug than the one it removes

The most transferable lesson here.

Dropping unmeasurable factors and renormalizing the rest (§4.1, instance
1) was **right on its own terms**. Combined with the 30-model minimum
that makes saturation unmeasurable for small populations, it made a
score resting on *one* factor arithmetically comparable to one resting on
*three* — and the thinnest score in the catalog ranked first. MirrorCode
sits at **95.1 on a single factor, its release date**, with 8 scored
models. [6]

Neither rule is wrong alone. They compose badly because **both change
what gets included in a computation**, and rules of that kind interact in
ways a single-rule reading misses. The mitigation is evidence tiers,
which make unequal evidence visible rather than arithmetically equal;
nothing makes the underlying arithmetic right.

**Before adopting a fix, work through how it interacts with the rules
already in place — especially any rule that changes what is included.**

A second instance from this session: `probes/impact.py`, the tool the
project mandates running before changing any scoring rule, printed a
column headed "% of total weight" that summed benchmark *health* rather
than weight. It therefore reported thin-tier benchmarks as carrying 1% of
model-side weight when the thin-tier exclusion guarantees they carry
**0%** — the column misreported the exact property it existed to check.
Both figures are now 0%. [7]

### 4.5 Silent averaging of repeated labels

The same source reports the same label for the same model many times, and
every one of those is silently averaged into a single displayed number.
Measured: [7]

- **15** (model, label, source) groups hold 2 or more entries, across
  **15 of 81** scored models
- **54 of 187** citations sit inside such a group
- spread: min 0.000, median 0.043, **max 0.620**
- **5** groups exceed the 0.08 scatter tolerance the benchmark side uses
- **4 of the 24** ranked models still hold such a group after D5 (13 of 33 before it)

The cause was found by inspecting the entries, and it decides the fix.
**The repeats are not disagreement — they are incomparable configurations
collapsed under one label:**

- *Hub model cards:* a different `metric_name` under one dataset. The 20
  `bigcode/gpt_bigcode-santacoder` entries under "MultiPL HumanEval
  (Python)" are pass@1, pass@10, pass@100 and exact_match. **pass@100
  exceeds pass@1 by construction**, so the mean is over different
  quantities, not repeated measurements. [7]
- *Epoch AI:* a distinguishing column this repo drops. Aider polyglot's
  export has an "Edit format" column; Qwen2.5-Coder-32B-Instruct scores
  8.0 with `diff` and 16.4 with `whole` — same model, same date, two
  protocols, averaged to 12.2.

This is §4.2 again (incomparable quantities in one field), arriving from
a different direction. Note that it is invisible to a check for
cross-*source* disagreement, of which this dataset contains none: a
five-fold spread under one label from one source was being meaned in
silence.

**Status: FIXED 2026-09-23 (decision D5, option iii).** Where the
benchmark documents a canonical protocol, the entry matching it is
weighted and the rest are shown as unweighted evidence with their
configuration named. HumanEval has one: EvalPlus, its maintained
leaderboard, publishes greedy-decoding pass@1, which is the column this
project's own benchmark side already reads. Where no canonical protocol
is documented — Aider polyglot's edit format, Terminal Bench's agent —
**nothing is picked and nothing is averaged**: every entry is shown
unweighted with a CURATE note saying what source would settle it.
Picking one unsourced would be inventing a protocol.

The cost, stated rather than buried: **the ranked population falls from
33 models to 24**, and nine models move to unweighted-only. [7] That is
the model side's real state, not a regression — those nine were ranked
on a mean of incomparable numbers.

A third case turned up in the data and needed its own treatment: two
entries with the *same* configuration and the *same* value are one
measurement reported twice, so the copy is marked as a duplicate rather
than averaged. Averaging identical numbers is arithmetically harmless
but it makes one datum look like corroboration.

### 4.6 Smaller instances, recorded for pattern-matching

- **HF v2 publishes each benchmark twice**: "GPQA Raw" (accuracy) and
  "GPQA" (rescaled so chance = 0). Reading the wrong column made GPQA's
  cross-source delta read 24.5 points when the truth was 7.9.
- **An alias merged two different benchmarks.** "SimpleQA" was an alias
  on SimpleQA Verified, so OpenAI's scores would have been attributed to
  Google's.
- **A model name matching a benchmark label proves nothing** about what
  the repository contains: `testaccount-ai/Qwen3.8-Max` once topped the
  table.
- **A constant can outlive the definition it was calibrated for.**
  `HEALTHY_SPREAD` was 0.20, set against top-10 spreads, and survived the
  move to a top-20% band, so every absolute saturation level in the
  catalog was on a scale nothing had been calibrated for.
- **A health score is not a constant — it decays every day.** Freshness
  is an age decay, so a benchmark's health falls whether or not anything
  in the repository changes. Measured: **mean catalog health falls 0.0286
  points per day.** [12] This was noticed only because a session crossed
  midnight and a figure quoted that morning no longer reproduced that
  evening. **Every health figure in this document is exact only on the
  date at the top of it**, and the drift check that guards these figures
  has to allow for it explicitly (`tests/test_doc_figures.py`, the
  `decays` flag).
- **A composite index is not a benchmark.**
  `artificial_analysis_coding_index` is 52 of 187 model-side citations
  and aggregates benchmarks this catalog already weighs separately, so
  those components were counted twice — once assessed, once inside an
  unassessed aggregate. It is now marked as a composite, excluded from
  weighting, and displayed with its known components. [7]
- **A claimed direction of effect is as inventable as a number.**
  "Raising the baseline will raise saturation" was written into a commit
  message as fact and was backwards: both saturation terms are fractions
  of (ceiling − baseline), so raising the baseline *lowers* both.
- **"Disjoint coverage" was three artifacts, not a gap.** Of the
  unrecognised citations, 52 are one composite index, 20 are one model's
  card listing variants of a single label, and roughly 50 distinct labels
  come from one model enumerating its multilingual suite.
  **Citation-weighted coverage is the wrong metric.** Model-weighted
  coverage — 34 of 81 models (42%) have at least one catalogued citation
  — is the meaningful one. [7]

---

## 5. Two constants that decide more than they should

### 5.1 `HEALTHY_SPREAD`

The spread across the measured band at which a benchmark counts as fully
discriminating. It is derived from the only noise floor this repo can
actually measure — the cross-source scatter of the same model scored by
two evaluators: [5]

```
n=8   median 0.0278   mean 0.0370   max 0.0805
3 × max = 0.2416  →  HEALTHY_SPREAD = 0.24
```

**The invented element is named rather than hidden: the multiplier 3.**
No derivation of this constant escapes one such choice; anchoring on the
observed spread distribution instead just moves the choice to a quantile.

And the sensitivity is itself a finding. Across the defensible range
0.084 (3× median scatter) to 0.358 (90th percentile of observed spreads),
mean catalog health moves from **56.2 to 43.8** and up to **19 of 28**
benchmarks change rank. [10] A constant whose plausible range reorders the
catalog is not a detail.

### 5.2 `MIN_SATURATION_POPULATION` — a cliff

Below 30 models, a top-20% band selects too few scores to mean anything,
so saturation is reported as unmeasurable rather than estimated. The
threshold is a **cliff**: crossing it does not degrade a benchmark's
score gradually, it removes a factor and moves the benchmark to a
different evidence tier.

Five benchmarks sit within 15 models of it: [6]

| benchmark | models | status |
|---|---:|---|
| MirrorCode | 8 | unmeasurable |
| The Agent Company | 16 | unmeasurable |
| SWE-Bench Verified | 35 | measured |
| FrontierCode | 35 | measured |
| GSO-Bench | 38 | measured |

Moving the threshold to 40 changes **3 tiers and 13 ranks**; moving it
anywhere from 20 to 35 changes nothing at all. [11] The instability is not
smooth — it is a step, and three benchmarks are standing within five
models of it.

A correction belonging here: an earlier report stated that the most
rank-unstable benchmarks "sit within a few models of the threshold". They
sit **5 to 8 models above** it. `docs/POPULATION_CLIFF.md` quantifies the
options — a derived threshold, a graded confidence, or reporting
saturation with an uncertainty interval from subsampling — and says what
each would invent. Nothing has been built.

---

## 6. What is open

1. **The forward test.** Sealed 2026-09-22, matures **2028-09-22**. See
   below.
2. **Model-side coverage is 42%** by the meaningful metric: 34 of 81
   scored models have at least one catalogued citation. [7] Adding
   benchmarks cannot close it — 68% of citations are unrecognised, and
   most of those are one composite index and two model cards.
3. **The repeated-label fix** (§4.5) is disclosed but undecided.
4. **`raw_benchmark_score` pools incomparable quantities** and
   within-source duplicates. Needs a per-category design change.
5. **Measurement gaps.** Reproducibility is measured for 8 of 28,
   saturation for 23. LiveCodeBench, MBPP and DS-1000 have no score
   source at all. [2]
6. **Verification gaps.** SWE-Bench Verified's item error *upper* bound
   is unknown — 0.164 is a floor derived from an audit of 138 of its 500
   problems (27.6%), and that sample was chosen *because* a model failed
   those problems consistently, so it is deliberately non-random. A 2026
   preprint reports the opposite error on a 49-task sample: 28.5% have
   tests weak enough to accept an incorrect patch. **The benchmark may
   be wrong in both directions at once**, and a single
   `item_error_rate` may be the wrong shape for it. HumanEval's 0.394 is
   not difficulty-controlled and no controlled replacement exists —
   Riddell et al.'s control group saw 16 of the 31 overlapping problems,
   so it cannot separate "the subset is easier" from "both groups are
   contaminated".
7. **Two penalties from one study may double-count.** SWE-Bench Verified
   is penalized for being memorized *and* for being misgraded. Those are
   independent defects with independent evidence, but they come from one
   audit of one non-random sample, so they are not independent
   *observations*. The scorer has no way to express that; the catalog's
   curation note is the only record of it.
8. **Saturation still depends on the submission pipeline** (§4.3). No fix
   proposed.
9. **Nobody but Claude Code has scored anything against the specificity
   rubric**, and four values are explicitly marked as assigned by Claude
   Code and not yet reviewed.

---

## 7. The forward test

The only live validation, and the only one that cannot be gamed, because
the outcome has not happened yet. Sealed 2026-09-22 in
`data/forward_test/sealed_2026-09-22.json`
(SHA-256 `4278081a7bebece9483cf1ec53d399d7aa3aeb137a652dcf5874c31eb02c562f`),
maturing **2028-09-22**.

**The claim:** benchmarks with high measurement health today will still
be discriminating at the horizon; those with low health will not.

**Sealed:** all 26 benchmarks in the catalog at that date, with health,
tier, every factor's value/weight/basis, measured saturation with its
population and model count, penalties and rubric dimensions — plus the
complete parameter set, because a prediction made under one parameter set
cannot be scored under another. MBPP and DS-1000 were added afterwards
and are correctly **out** of it.

**Pass criterion, fixed in advance.** Among same-tier pairs where health
and release date predict *opposite* outcomes: PASS at ≥70% of discordant
pairs with at least 10 such pairs; FAIL at ≤40%; INCONCLUSIVE otherwise,
including if fewer than 10 discordant pairs exist. The 10-pair minimum is
the lesson of every previous test here — the hindcast had 4 and Candidate
1 had 1.

**The age baseline is fixed in advance too:** rank by release date,
newest first, within tier, scored on exactly the same pairs and reported
beside the scorer's number every time.

> **The scorer does not pass by passing. It passes by beating the
> baseline.** A result where both reach 70% is a pass for the calendar
> and INCONCLUSIVE for the scorer, and must be reported that way.

Until it returns, the honest answer to "does the scoring work?" is **no
test has shown that it does.**

---

## Footnotes — the command behind each figure

All run 2026-09-22 against committed data; nothing touches the network.

1. `python probes/findings.py humaneval`
2. `python probes/findings.py coverage`
3. `python probes/findings.py backtest`
4. `python probes/findings.py candidate1`
5. `python probes/findings.py noise`
6. `python probes/findings.py cliff`
7. `python probes/findings.py modelside`
8. `python probes/findings.py correlations`
9. `python backtest.py --sweep`
10. `python probes/impact.py parameter HEALTHY_SPREAD 0.084 0.197 0.24 0.358`
11. `python probes/impact.py parameter MIN_SATURATION_POPULATION 20 25 30 35 40`
12. `python probes/findings.py decay`
13. `python probes/hindcast.py`
14. `python probes/arc_agi_population.py` — **needs the network**, and is
    the only footnote here not run by CI. Everything else is smoke-tested
    by `tests/test_diagnostics.py` on every push, and the figures are
    checked against this document by `tests/test_doc_figures.py`.
15. `python probes/config_rows.py`

Test suite: `python -m pytest -q` — 279 passing as of this writing. The
suite runs **offline against committed data**, which means a dependency
upgrade can break every fetcher in the repository and the suite will
still pass.
