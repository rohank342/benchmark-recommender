# Backtest: does the trust score agree with a decision already made?

**Run it:** `python backtest.py` (add `--sweep` for the diagnostics).

**Result at 12 benchmarks: 10/12, separation LOST by 1.4 points. The scorer
gets one pair the wrong way round.** No weights were changed in response.

**This used to pass.** At 8 benchmarks it scored 8/8 with perfect separation
and an 8.2-point margin. Adding the four missing benchmarks — completing
both sides of the decision being tested — turned a pass into a partial
failure. The earlier result was a small-sample result, and reporting it as
validation would have been wrong.

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
| 1 | GPQA Diamond | kept | 73.9 | 33 |
| 2 | MATH Level 5 | kept | 71.6 | 29 |
| 3 | BIG-Bench Hard | kept | 63.5 | 81 |
| 4 | MMLU-Pro | kept | 53.2 | 608 |
| 5 | IFEval | kept | 48.9 | 608 |
| 6 | **MMLU** | **retired** | **45.0** | 172 |
| 7 | **MuSR** | **kept** | **43.6** | 608 |
| 8 | ARC | retired | 42.3 | 121 |
| 9 | Winogrande | retired | 42.0 | 124 |
| 10 | GSM8K | retired | 40.6 | 142 |
| 11 | TruthfulQA | retired | 36.8 | 7,095 |
| 12 | HellaSwag | retired | 28.2 | 97 |

|  | HF retired | HF kept |
|---|---:|---:|
| **scorer: retire** | 5 | 1 |
| **scorer: keep** | 1 | 5 |

**One inversion**: MMLU (retired) scores 1.4 points above MuSR (kept). Every
other benchmark lands on the correct side.

### Why the miss happens

MuSR's `task_specificity` is 0.3 — my hand-assigned judgement that synthetic
murder-mystery puzzles don't map onto real work. That judgement is 20% of
its score and is what drags it below MMLU. The scorer's weakest, least
defensible input produces its only error.

That is worth sitting with. It is not a data problem that more scraping
fixes.

---

## The diagnostics, which are worse than the headline

### One factor can no longer do it

| ranking by | 8-benchmark result | 12-benchmark result |
|---|---|---|
| discrimination alone | **8/8, separated** | **8/12, not separated** |
| freshness alone | 6/8, not separated | 10/12, not separated |
| specificity alone | 6/8, not separated | 10/12, not separated |
| reproducibility alone | 4/8, not separated | 6/12, not separated |
| **release date alone (no scoring)** | **6/8** | **10/12** |

The earlier headline — "discrimination alone gets 8/8, so measured
saturation is doing the work, not age" — **does not survive**. At twelve
points discrimination alone gets 8/12, worse than ranking by publication
date.

**And the trivial baseline now ties the full scorer.** Sorting by release
date and calling the newer half "kept" gets 10/12, exactly what the four
weighted factors achieve. On this expanded test, the scoring machinery adds
nothing over "newer benchmarks are better."

### Sensitivity

12/12 is reachable, but the settings disagree about how:

- **freshness ≥ 0.30** → 12/12, separated (gap +5.5 to +18.5)
- **reproducibility = 0.10** → 12/12, separated (gap +5.9)
- **specificity 0.40–0.50** → 12/12, separated (gap +0.5 to +1.5)
- **discrimination**: never reaches 12/12 at any tested weight

Three different single-weight changes each "fix" the test, pulling in
different directions. That is the signature of fitting to twelve data
points, not of finding the right weights. **No weights were changed.**

---

## What changed as a result

**Nothing in the scorer.** The test was expanded, run, and reported. Tuning
after seeing the answer would convert a prediction into a retrofit, and the
sensitivity sweep shows several mutually inconsistent ways to do it.

Two tests that asserted the old perfect result were rewritten to assert the
current one, including pinning the known inversion, so the failure is
recorded in the suite rather than papered over.

The honest summary is now: *the scorer is wrong about one of twelve pairs,
its only error traces to its least defensible input, and on this test it
does not outperform sorting by publication date.*

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
