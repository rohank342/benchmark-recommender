# Backtest: does the trust score agree with a decision already made?

**Run it:** `python backtest.py` (add `--sweep` for the diagnostics).

**Result at 12 benchmarks: 10/12, separation lost by 28.9 points.** One
benchmark lands on the wrong side. No weights were changed in response.

*Updated 2026-09-22 (fourth run). Two input changes, both argued from
evidence and neither made with this test in view: unmeasurable factors
stopped contributing (8/12 → 10/12, gap −20.6 → −10.3), then saturation
moved to a percentile definition (gap → −28.9). **Every earlier number
in this document was computed under a saturation definition now known to
be artifactual** — see [SATURATION_MEASUREMENT.md](SATURATION_MEASUREMENT.md).
They are superseded, not contradicted.*

**The one miss is now MATH Level 5**, which HF kept and which ranks 11th
of 12 — because its 2024 population is 29 models, below the minimum a
percentile needs, so its discrimination is dropped and it is scored on
freshness and reproducibility alone. That is a limit of the data, not a
finding about MATH Level 5.

*Updated 2026-09-22 (third run): the score was split into measurement
health and task relevance, and the backtest scores HEALTH. Specificity is
no longer in the score, which moved this from 10/12 to 8/12 — exactly
what the exploratory run in [SCORE_SPLIT_PROPOSAL.md](SCORE_SPLIT_PROPOSAL.md)
predicted before the split was adopted. The split was adopted on the
argument that health and relevance are different questions, not on any
test result, and this is the test result it cost.*

**One consequence worth stating: the specificity sensitivity analysis
below is now vacuous.** Relevance is not in the score, so no rubric
change to any of the twelve can move this result at all. A test pins
that.

*Updated 2026-09-21 (second run): quantifying GSM8K's contamination
effect from GSM1k's per-model table — a CURATE item that predates this
result and was identified as the fix before it existed — moved GSM8K from
62.5 to 59.7 at the cutoff and narrowed the gap from 20.1 to 17.3. The
verdict did not change: still 10/12, still GSM8K ranked 4th, still no
separation.*

*Updated 2026-09-21, after two owner decisions: specificity is now
computed from [rubric v2](SPECIFICITY_RUBRIC.md), and an unquantified
contamination flag no longer carries a numeric penalty
([METHODOLOGY.md](METHODOLOGY.md)). Both were committed from their own
evidence before this was run.*

**The verdict is now a stable failure, not a close one.** The previous
run was 10/12 with a 0.6-point gap that a 0.04 change in one unreviewed
judgement could flip. This run is 10/12 with a 20.1-point gap that
**nothing** in the sensitivity analysis below can flip. The scorer has
stopped being marginally wrong and started being clearly wrong about
separation.

**This used to pass.** At 8 benchmarks it scored 8/8 with perfect
separation and an 8.2-point margin. Completing both sides of the decision
turned that into a partial failure, and the two decisions above widened
it.

---

## The test

In June 2024 Hugging Face retired six benchmarks from the Open LLM
Leaderboard because they had saturated — ARC, HellaSwag, MMLU, TruthfulQA,
Winogrande, GSM8K — and replaced them with a harder set: MMLU-Pro, GPQA,
MuSR, IFEval, BBH and MATH Lvl 5.

All twelve are now catalogued. Scored **as of 2024-06-01**, do the retired
six rank below the replacements? Six-and-six means 924 possible splits, so
chance agreement is far less likely than it was at four-and-four (70).

### Why this isn't circular

Every curated claim carries an `evidence_dates` entry recording when it
became public. The retirement-derived saturation flags are dated
`2024-06-26`, so as-of scoring at `2024-06-01` cannot see them. The same
gate excludes models uploaded after the cutoff, studies published after it,
undated evidence, and cross-source agreement entirely. Undated models are
dropped rather than assumed old.

`tests/test_backtest.py` pins each guard. They are the load-bearing part;
the score means nothing without them.

---

## What it showed

| rank | benchmark | actual | trust | models |
|---:|---|---|---:|---:|
| 1 | MATH Level 5 | kept | 71.6 | 29 |
| 2 | GPQA Diamond | kept | 65.9 | 33 |
| 3 | BIG-Bench Hard | kept | 63.5 | 81 |
| 4 | **GSM8K** | **retired** | **59.7** | 142 |
| 5 | MMLU-Pro | kept | 52.2 | 608 |
| 6 | IFEval | kept | 47.9 | 608 |
| 7 | MMLU | retired | 45.0 | 172 |
| 8 | ARC | retired | 43.3 | 121 |
| 9 | **MuSR** | **kept** | **42.4** | 608 |
| 10 | Winogrande | retired | 42.0 | 124 |
| 11 | TruthfulQA | retired | 32.8 | 7,095 |
| 12 | HellaSwag | retired | 27.0 | 97 |

|  | HF retired | HF kept |
|---|---:|---:|
| **scorer: retire** | 5 | 1 |
| **scorer: keep** | 1 | 5 |

### Where it goes wrong, and why

**GSM8K (retired) ranks 4th of 12**, above three benchmarks HF kept. It
sits 17.3 points above the weakest kept benchmark, and that single
placement is the whole of the lost separation.

The cause is traceable to one decision. GSM8K's contamination flag —
from Scale AI's GSM1k study — had no usable rate or effect at the 2024
cutoff, and under the old rule that cost it a flat penalty. Treating an
unquantified flag as a warning moved it from **40.6 to 62.5**. Without
that change the best-ranked retired benchmark would be MMLU at 45.0 and
the gap would be −2.6.

So the contamination decision is defensible on its own terms and is also
the reason this test now fails badly. Both things are true. The decision
was not made to affect this test and was committed before it was run.

**MuSR (kept) ranks 9th**, below three retired benchmarks. Rubric v2
moved its specificity from 0.30 to 0.20 — further from the 0.34 that
would once have fixed the older, narrower failure.

---

## Sensitivity: can reviewer-sized noise change the answer?

The rubric warns that specificity differences below ~0.2 are noise —
about one reviewer disagreeing on two of five dimensions. So: for each of
the 12 benchmarks, change each dimension score by ±1 (staying in 0–2),
one change at a time, and rescore.

**82 single-point changes. Zero change the verdict.**

| | |
|---|---|
| correct count across all 82 runs | **10/12 every time** |
| separation across all 82 runs | **lost every time** |
| gap range | −22.1 to −18.1 (at the −20.1 baseline; the gap is now −17.3 and the analysis has not been rerun) |

None of these changes were applied.

**What this means, and what it does not.** The verdict is robust to
single-reviewer disagreement, so this result cannot be dismissed as noise
in the specificity judgements — which is exactly what could have been
said about the previous 0.6-point run. That is a real improvement in what
the test can tell us.

It is not good news. The thing that is now robust is a **failure**. A
20-point gap is not a near miss, and no plausible re-scoring of the most
subjective input closes it.

---

## The diagnostics, which are worse than the headline

### One factor can no longer do it

| ranking by | 8 benchmarks | 12, before the decisions | 12, now |
|---|---|---|---|
| discrimination alone | **8/8, separated** | 8/12 | **8/12** |
| freshness alone | 6/8 | 10/12 | **10/12** |
| specificity alone | 6/8 | 10/12 | **8/12** |
| reproducibility alone | 4/8 | 6/12 | **6/12** |
| **release date alone (no scoring)** | **6/8** | **10/12** | **10/12** |

The earliest headline — "discrimination alone gets 8/8, so measured
saturation is doing the work, not age" — **does not survive**. At twelve
points discrimination alone gets 8/12, worse than ranking by publication
date.

**The trivial baseline still ties the full scorer**: sorting by release
date and calling the newer half "kept" gets 10/12, exactly what the four
weighted factors achieve. On this test the scoring machinery adds nothing
over "newer benchmarks are better."

Specificity alone fell from 10/12 to 8/12 under rubric v2. That is worth
sitting with: the rubric was adopted to make specificity defensible, and
the more defensible version is a *worse* standalone predictor of this
particular decision. Either the rubric is wrong, or HF's 2024 decision
tracked something other than how task-shaped a benchmark is. The second
is more likely — HF's stated reasons included cost and where they wanted
the field to climb — but this test cannot separate the two.

### Weight sweep

| setting | result |
|---|---|
| freshness ≥ 0.50 | 12/12, separated (gap +1.3 to +3.2) |
| every other single-weight change tested | 10/12 or worse, never separated |

**Only one lever now reaches 12/12, and it is the age proxy.** Before
these decisions, four different single-weight changes each produced a
pass, pulling in incompatible directions — the signature of fitting to
twelve data points. That ambiguity is gone, and what replaced it is
worse: the only way to pass this test is to weight *freshness* at 0.50,
i.e. to make the scorer behave more like the calendar baseline it
already fails to beat.

Raising discrimination — the headline factor — never reaches 12/12 at
any tested weight, and 0.60 makes it worse (8/12).

**No weights were changed.**

---

## What changed as a result

**Nothing in the scorer's weights.** Two owner decisions changed inputs
(rubric v2, contamination treatment (c)); both were argued and committed
from their own evidence before this was run, and neither was chosen for
its effect here. The test was then run once and reported as-is.

The tests that pinned the previous failure were re-pinned to this one, so
the suite records the current reality rather than a historical one.

The honest summary is now: *the scorer places a retired benchmark fourth
of twelve, loses separation by 20 points, cannot be rescued by any
single-point change to its most subjective input, and does not outperform
sorting by publication date.*

---

## What this does not establish

**It never validated the weights, and now it doesn't even pass.** A
backtest can falsify; this one now partially does.

**The ground truth is a judgement, not a measurement.** HF retired a set for
stated reasons including saturation, cost, and a view about where the field
should climb. MuSR being "kept" means HF picked it in 2024, not that it was
good.

**The as-of reconstruction is still imperfect.** Curated fields —
specificity, evaluator counts — are recorded as of today and are not
time-varying, so the scorer uses 2026's view of how task-shaped a benchmark
is while pretending it is 2024. Given that specificity causes the only miss,
this matters more than it did before.

**Twelve points is still small.** Better than eight, still one decision.

---

## What would actually move this forward

1. **Interrogate specificity.** It is 20% of every score, entirely
   judgement, and the direct cause of the only error. Either ground it in
   something checkable or reduce its weight — but decide that on its merits,
   not because it fixes this test.
2. **A second dated decision.** Any leaderboard retiring or adding a
   benchmark with stated reasons is another independent draw. One decision
   cannot distinguish a good scorer from one tuned to a single event.
3. **Beat the age baseline, or admit it.** If four weighted factors cannot
   outperform sorting by release date on the only test available, the burden
   is on the scorer to show what it adds.
4. **A forward test.** This asks whether saturated benchmarks score low. The
   claim the tool actually makes is that high scores predict a benchmark
   still discriminating in two years. Untested, and unfalsifiable until time
   passes.
