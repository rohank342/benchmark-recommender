# Second test — pre-registration

**Status: design only. Nothing has been run.** No as-of score has been
computed for any candidate event in this document. Awaiting the owner's
approval of the event list; changes after approval go in as new commits,
not rewrites.

## Why a second test

The existing backtest (docs/BACKTEST.md) gets 10/12 and cannot be
distinguished from sorting by release date, which also gets 10/12. Across
those twelve, age and measured saturation are uncorrelated (r = +0.010)
while age alone predicts the retire/keep label at r = +0.793. Measured
saturation's entire incremental contribution over age is two pairs out of
36, both involving one benchmark.

A second test is only worth running if it can separate the two. That means
it must contain events where **the age baseline and the scorer predict
different outcomes**. An event where both predict the same thing cannot
tell them apart, no matter how well-documented it is.

---

## THE STRUCTURAL PROBLEM, found while applying that filter

This is the main result of the design exercise and it is bad news.

**Benchmark replacement events are old→new by construction.** A lab or
leaderboard retires a saturated benchmark and adopts a harder, newer one.
That is what the event *is*. So on almost every such event the age
baseline is right by definition, and the event cannot discriminate.

Applying the filter to the candidate list killed most of it:

| candidate | age baseline | keeps? |
|---|---|---|
| aider edit → polyglot (2024-12-21) | older retired, newer kept → **right** | ✗ |
| ARC-AGI-1 → ARC-AGI-2 (2025-03-24) | older retired → **right** | ✗ |
| GLUE → SuperGLUE (2019-05-02) | older retired → **right** | ✗ |
| OpenAI: SWE-bench Verified → SWE-bench Pro (2026-02-23) | older retired → **right** | ✗ |
| Epoch AI benchmark reviews (2026-08/09) | mixed, but wrong instrument | ✗ |
| SWE-bench Verified vs benchmarks *older than it* still in use | **wrong** | ✓ (weak) |
| ARC-AGI-1 as old-but-unsaturated | **wrong** | ✓ (needs building) |

Only two survive, and only one of those is runnable today. **The supply of
discriminating events is the binding constraint on this project, not
engineering effort.** Anyone expecting a second test to rescue the scorer
should read that table first.

---

## Candidate 1 — OpenAI abandons SWE-bench Verified (2026-02-23)

### Verification

Published 2026-02-23 as "Why SWE-bench Verified no longer measures
frontier coding capabilities".
→ https://openai.com/index/why-we-no-longer-evaluate-swe-bench-verified/

**Verification caveat, stated because this is a pre-registration:**
openai.com returns 403 to automated fetches, so this repo cannot retrieve
the primary source. The date, the stated reasons and the recommendation of
SWE-bench Pro were confirmed via search and against secondary carriers
quoting the text verbatim. Treat the citation as primary-sourced but
not primary-*retrieved*.

**Stated reasons** (three, and only the first is about saturation):

1. Saturation: the top score moved only from 74.9% to 80.9% over six
   months.
2. Item quality: of 138 audited hard tasks, 59.4% had flawed test design.
3. Contamination: the benchmark and its repositories are open source and
   widely discussed, "which makes avoiding contamination difficult".

OpenAI recommends **SWE-bench Pro** as the replacement.

### Why the obvious framing does NOT count

The natural reading — retired: SWE-bench Verified (2024-08-13); kept:
SWE-bench Pro (2025-09) — is another old→new event. Age predicts the
retirement correctly. **Dropped under the filter.**

### The framing that does count

SWE-bench Verified was **1.5 years old and among the newest benchmarks in
the catalog** when a frontier lab publicly abandoned it. Compare it
against benchmarks that are **older** and were still in active use:

- **Age baseline predicts:** SWE-bench Verified (2024-08-13) ranks ABOVE
  GPQA Diamond (2023-11-20), because it is nine months newer. Age is
  therefore **wrong** about which one the field stopped trusting.
- **Scorer predicts, if discrimination carries information:** SWE-bench
  Verified ranks BELOW GPQA Diamond at the as-of date, because its
  measured saturation is already high.

These differ. **This event counts.**

### As-of date and leakage audit

**As-of: 2026-02-01**, three weeks before the post.

Every SWE-bench Verified claim in the catalog derives from that post and
must be invisible. Audited:

| claim | evidence date | visible at 2026-02-01? |
|---|---|---|
| `item_error_rate` = 0.164 | 2026-02-23 | **no** |
| `contamination_flagged` = True | 2026-02-23 | **no** |
| GPQA `saturation_flagged` | 2026-09-01 | **no** |
| OSWorld — any claim | none recorded | n/a |

At 2026-02-01 SWE-bench Verified therefore carries **no penalties at
all**. Its score comes purely from the four factors, which is exactly what
this test should be probing. This is a hard gate: if any of those claims
becomes visible at the as-of date, the run is void.

### Feasibility — probed, not assumed

Dated models available before 2026-02-01, from the committed Epoch export
(`SATURATION_TOP_K` is 10, so 10 is the minimum):

| benchmark | dated total | before 2026-02-01 | after |
|---|---:|---:|---:|
| SWE-bench Verified | 35 | **18** ✓ | 17 |
| GPQA Diamond | 311 | **196** ✓ | 115 |
| OSWorld | 20 | 19 ✓ | **1** |
| Aider polyglot | 72 | 72 ✓ | **0** |
| The Agent Company | 16 | 16 ✓ | **0** |

Runnable with data already in the repo. No fetching required.

### Three weaknesses of this event, recorded before running it

1. **The comparison mixes deciders.** OpenAI abandoned SWE-bench Verified.
   Nobody correspondingly "kept" GPQA Diamond. The HF event had one
   decider making both calls; this does not.
2. **The abandonment did not stick.** 17 models were evaluated on
   SWE-bench Verified *after* OpenAI's post. The field did not follow, so
   "abandoned" describes one lab's practice, not the benchmark's status.
3. **OSWorld cannot serve as a comparator**, despite being the obvious
   choice on age. Only **one** model was evaluated on it after the as-of
   date, so by the same measure that indicts SWE-bench Verified, OSWorld
   went quiet too. Using it would be picking a comparator that fails its
   own criterion. **GPQA Diamond is the only viable comparator**, which
   reduces this event to a **single pair**.

---

## Candidate 2 — ARC-AGI-1 as old-but-still-discriminating (NOT YET BUILDABLE)

The highest-value candidate and the only one that puts a case in the cell
the current backtest has zero examples of.

### Verification

Released 2019 (Chollet, "On the Measure of Intelligence", arXiv
1911.01547). Frontier models remained at roughly 5% into 2024; the
benchmark was first broken by o3 in December 2024 at 75.7–87.5%.
→ https://arcprize.org/blog/oai-o3-pub-breakthrough (2024-12-20)
→ https://arcprize.org/blog/announcing-arc-agi-2-and-arc-prize-2025 (2025-03-24)

Note the 2025-03-24 announcement does **not** state that ARC-AGI-1 was
saturated; it frames ARC-AGI-2 as raising the bar. The saturation event is
the o3 result, not the successor's launch.

### Predictions

At an as-of date of **2024-06-01** — the same cutoff as the existing
backtest, six months before o3:

- **Age baseline predicts:** ARC-AGI-1 is 4.6 years old, older than every
  "kept" benchmark in the current test. Age ranks it at the bottom and
  says it should have been retired. Age is **wrong** — it was a live,
  respected benchmark that had not been beaten.
- **Scorer predicts, if discrimination carries information:** near-zero
  saturation (leaders under 5% of the usable range), so it should rank
  HIGH despite its age.

These differ as sharply as any event on the list. **This event counts,
and it is the one worth paying for.**

### What adding it would take

1. **Catalog entry.** Release date, dataset size (400 public evaluation
   tasks), `holdout` — ARC-AGI runs a semi-private set verified by ARC
   Prize, which is `partial_holdout` or `private_holdout` depending on
   which set is scored. That choice must be made from their policy page,
   not assumed.
2. **A dated score distribution, which the repo does not have.** Epoch's
   export does not include ARC-AGI. Sources:
   → https://arcprize.org/leaderboard (JS-rendered; likely needs the
     underlying JSON, not scraping)
   → the arcprize HF datasets org
   → ARC Prize 2024 Technical Report, arXiv 2412.04604, for dated results
3. **A decision about which scores are comparable.** ARC Prize verifies
   semi-private results but marks public-set results self-reported.
   Mixing them would violate the cross-source rules in
   `cross_source.py`. Only one population should be used.
4. **Estimated effort:** a new fetcher plus curation. This is the single
   most valuable open engineering task in the project.

---

## Candidates examined and dropped

**aider: original edit benchmark → polyglot (2024-12-21).** Verified from
the primary source: the original "was saturating as the top scores
approached and then surpassed 80%", top score 84.2% solving 112 of 133,
leaving 21 unsolved. → https://aider.chat/2024/12/21/polyglot.html
Dropped: old→new, age is right, predictions agree. Also, aider polyglot
has **0** models evaluated after 2026-02-01 in our data.

**ARC-AGI-1 → ARC-AGI-2 (2025-03-24)** and **GLUE → SuperGLUE
(2019-05-02, arXiv 1905.00537)**. Both verified, both old→new, both
dropped for the same reason. GLUE additionally predates any score data the
repo can reach.

**Epoch AI benchmark reviews (Aug–Sep 2026).** The most promising find of
this search, and dropped for a specific reason. Epoch publishes dated
verdicts by one consistent decider against published criteria — Verified /
Flawed / Not enough information — covering 15 benchmarks, six of which are
in this catalog:

| benchmark | verdict | review date |
|---|---|---|
| SimpleQA Verified | Verified | 2026-09-10 |
| FrontierCode | Not enough info | 2026-09-11 |
| DeepSWE v1.1 | Flawed | 2026-09-07 |
| Terminal-Bench 4.0.0 | Flawed | 2026-09-04 |
| SWE-bench Verified | Flawed | 2026-09-03 |
| Humanity's Last Exam | Flawed | 2026-08-11 |

→ https://epoch.ai/data/benchmark-reviews-documentation/included-benchmarks

**Why it is the wrong instrument:** Epoch's bar is "≥20% of inspected
sample contains errors, or an issue that corrupts grading at scale". That
is an **item-quality** judgement, not saturation. A test against these
verdicts would test `item_error_rate`, which is recorded for only 4 of 26
benchmarks and is `None` for DeepSWE, Terminal-Bench and HLE — so the
scorer would have nothing to predict with on three of the six.

**It is also circular for SWE-bench Verified**: this catalog's
`item_error_rate` cites Epoch's review of OpenAI's audit as its source.
Using Epoch's verdict as ground truth would be scoring against our own
evidence. The dates would technically pass (our evidence is 2026-02-23,
their review 2026-09-03) while the substance would not.

**Recorded as a strong candidate for a different test** — "does the
item-quality penalty agree with an independent reviewer?" — which is worth
running once more benchmarks carry an audited rate.

**Artificial Analysis Intelligence Index v4.0 (2026-01-06) and v4.3
(2026-09-07).** v4.3 is verified from the changelog: AutomationBench-AA
replaced τ³-Banking and Terminal-Bench went v2.1 → v4.0.
→ https://artificialanalysis.ai/changelog
Dropped for now: the v3 component list could not be retrieved from a
primary source, so the dropped-versus-kept split cannot be established,
and the benchmarks involved (τ³-Banking, SciCode, AA-Briefcase, CritPt,
GDPval-AA, AA-Omniscience) are not in the catalog. **This is the best
remaining lead for a multi-event test** — the changelog is dated, itemised
and maintained by one decider — but it needs the historical component
lists and roughly six new catalog entries before any of it can be scored.

---

## Pre-registered criteria

Written before computing any as-of score for these events.

### Gate 0 — leakage (applies to every event, blocking)

Before any score is read, assert for every benchmark in the event that no
claim derived from the event is visible at the as-of date. Any violation
voids the run. For Candidate 1 the specific assertions are
`item_error_rate` and `contamination_flagged` on SWE-bench Verified, and
`saturation_flagged` on GPQA Diamond, all invisible at 2026-02-01.

### Candidate 1 — pass/fail

Let `S` = SWE-bench Verified's trust at 2026-02-01, `G` = GPQA Diamond's.

- **PASS:** `S < G`. The scorer places the benchmark that a frontier lab
  was about to abandon below an older one that stayed in use — the
  opposite of the age ordering.
- **FAIL:** `S > G`. The scorer agrees with age and is wrong with it.
- **Margin, pre-registered as secondary:** a pass with `G − S ≥ 2.0`
  points is a clear pass; `0 < G − S < 2.0` is recorded as a **narrow
  pass** and must be reported as such. The 2.0 is arbitrary and is fixed
  now precisely so it cannot be chosen afterwards.
- **Also recorded, not scored:** which factor drives the gap. If `S < G`
  is produced by freshness or specificity rather than discrimination, the
  event has not demonstrated what it was built to demonstrate, and the
  write-up must say so even though the test passed.

### Candidate 2 — pass/fail (when built)

Let `A` = ARC-AGI-1's trust at 2024-06-01.

- **PASS:** `A` ranks in the top half of the twelve-benchmark cohort
  scored at the same date, despite ARC-AGI-1 being older than all of them.
- **FAIL:** `A` ranks in the bottom half, i.e. the scorer reproduces the
  age ordering on the clearest available counterexample.
- **Void:** fewer than 10 dated models before the as-of date, or a mixed
  verified/self-reported population.

### Overall criterion

**This test cannot validate the scorer, and a pass must not be reported as
if it could.** With Candidate 1 runnable alone, the test is a **single
binary comparison**: a coin flip passes it 50% of the time. Candidates 1
and 2 together are two comparisons — 25% by chance.

Therefore, pre-registered:

- The test is run as a **falsification check only**.
- A pass is reported as "the scorer survived a test it could have failed",
  never as evidence that it works.
- The result is reported **whatever it is**, in the same commit as the
  run, with the criteria above quoted from this document.
- No weight, threshold or curated value is changed in response to the
  result. If the result suggests a change, that change is a separate
  decision made on its own evidence, in a later commit, with this
  document cited.

### What would count as evidence AGAINST the scorer

Stated explicitly so it cannot be explained away afterwards:

1. **`S > G` on Candidate 1.** The scorer ranks a benchmark a frontier lab
   was about to abandon above an older one that stayed in use — agreeing
   with the age baseline on the one pair built to separate them. Combined
   with the existing backtest, this would mean the scorer has never been
   shown to beat age on any discriminating comparison.
2. **A pass driven by freshness or specificity rather than
   discrimination.** That would mean the measured factor contributed
   nothing and the result came from a judgement call and a calendar.
3. **`A` in the bottom half on Candidate 2.** ARC-AGI-1 at mid-2024 is the
   clearest old-but-unsaturated case available. A scorer whose
   discrimination factor cannot rescue it from its age has no
   demonstrated ability to detect an un-saturated benchmark.
4. **Any need to adjust the design after seeing a score.** If the criteria
   above turn out to be unworkable only once results are visible, that is
   itself evidence the test was not well-specified, and the honest report
   is "the design failed", not a revised design.

---

## What was inspected while writing this

For transparency about what could have leaked into the design:

- **Looked at:** release dates, `evidence_dates`, catalog flags, and
  counts of dated models before and after the as-of dates (population
  sizes, not scores). Primary and secondary sources for each event.
- **Not looked at:** any as-of trust score, factor value or saturation
  measurement for SWE-bench Verified, GPQA Diamond, OSWorld or any other
  candidate at any candidate as-of date. `backtest.py` was not run.
- Today's scores for the catalog are known from previous work and were
  not consulted for these events.

---
---

# RESULT — Candidate 1, run 2026-09-21

Run once, as registered, after rubric v2 and the contamination decision
were committed. **No part of the design was modified.** One-pair
falsification check.

## Gate 0 — leakage: PASSED

| claim | visible at 2026-02-01? |
|---|---|
| SWE-Bench Verified `item_error_rate` | no |
| SWE-Bench Verified `contamination_flagged` | no |
| GPQA Diamond `saturation_flagged` | no |

Dated models before the as-of date: SWE-Bench Verified 18, GPQA Diamond
196. Both clear the minimum of 10.

## The numbers

| | SWE-Bench Verified | GPQA Diamond |
|---|---:|---:|
| released | 2024-08-13 | 2023-11-20 |
| discrimination (×0.40) | 0.288 → 11.53 *(measured, 18 models)* | 0.339 → 13.55 *(measured, 196)* |
| freshness (×0.20) | 0.601 → 12.01 | 0.466 → 9.32 |
| reproducibility (×0.20) | 1.000 → 20.00 *(curated)* | 1.000 → 20.00 *(curated)* |
| specificity (×0.20) | 1.000 → 20.00 | 0.200 → 4.00 |
| penalties | none | none |
| **trust at 2026-02-01** | **S = 63.5** | **G = 46.9** |

`G − S = −16.6`

## Verdict: **FAIL**

The registered criterion:

> **FAIL:** `S > G`. The scorer agrees with age and is wrong with it.

`S > G` by 16.6 points. The scorer ranks the benchmark a frontier lab was
about to publicly abandon **above** the older one that demonstrably stayed
in use — the same ordering the age baseline gives, on the one pair the
test was built to separate them.

The registered consequence, quoted:

> Combined with the existing backtest, this would mean the scorer has
> never been shown to beat age on any discriminating comparison.

That is now the situation. **The scorer has not beaten the age baseline on
a single discriminating comparison anywhere in this project.**

## The one thing that went the right way

Pre-registered as "recorded, not scored": which factor drives the gap.

| factor | contribution to `G − S` |
|---|---:|
| **discrimination** | **+2.02** |
| reproducibility | 0.00 |
| freshness | −2.69 |
| **specificity** | **−16.00** |

**Discrimination pointed the right way.** The measured factor — the one
the project is actually about — ranked GPQA Diamond as the better
benchmark at that date, correctly. It was then overwhelmed by
specificity, which is 20% of the score, has no measurement behind it, and
contributed −16.00 points on its own.

Specificity here is SWE-Bench Verified at 1.00 (real GitHub issues, real
patches, real tests) against GPQA Diamond at 0.20 (four-option multiple
choice). Both are defensible readings of rubric v2. The rubric is doing
exactly what it says it does — and on this test it is what produces the
wrong answer, by an order of magnitude more than the measured factor
produces the right one.

That is a sharper result than a plain FAIL. It is not "the scorer cannot
see saturation"; it is **"the scorer can see saturation and its own
judgement factor outvotes it 8:1."**

## What was not done

No weight, threshold or curated value was changed in response. Per the
registration, any change suggested by this result is a separate decision
made on its own evidence, in a later commit, citing this document.

## Note on comparability

The registration was written before rubric v2 and the contamination
decision landed, so the absolute scores here are not the ones that would
have been produced on the day it was written. The owner sequenced the run
after those changes deliberately. The design — as-of date, comparator,
gate, criteria, margin — was followed exactly as registered.
