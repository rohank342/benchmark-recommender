# Backtest: does the trust score agree with a decision already made?

**Run it:** `python backtest.py` (add `--sweep` for the sensitivity analysis).

**Result: 8/8, with perfect separation and an 8.2-point margin. No weights
were changed as a result** — the test passed as it stood, and tuning after
seeing the answer would have destroyed its value as evidence.

**But read [What this does not establish](#what-this-does-not-establish)
before quoting the 8/8.** Eight benchmarks and one decision is a very small
ground truth.

---

## The test

In June 2024 Hugging Face retired six benchmarks from the Open LLM
Leaderboard because they had saturated — ARC, HellaSwag, MMLU, TruthfulQA,
Winogrande, GSM8K — and replaced them with a harder set: MMLU-Pro, GPQA,
MuSR, IFEval, BBH and MATH Lvl 5.

That is a dated expert judgement about exactly the property this project
scores. Four retired and four replacement benchmarks are in this catalog
(Winogrande, GSM8K, MuSR and IFEval are not). Scored **as of 2024-06-01**,
do the retired four rank below the replacements?

### Why this isn't circular

The saturation flags on the retired four exist *because* of the retirement.
Handing them to a scorer being tested against that retirement would be
marking its own homework.

Every curated claim in the catalog carries an `evidence_dates` entry
recording when it became public. The retirement-derived flags are dated
`2024-06-26`, so as-of scoring at `2024-06-01` cannot see them. The same
gate excludes:

- **Models uploaded after the cutoff.** Saturation is measured only over
  models that existed in May 2024. Undated models are dropped rather than
  assumed old — including one that might postdate the cutoff would import
  the future.
- **Studies published after the cutoff.** MMLU's 27.7% contamination rate
  is a 2025 finding and is invisible at the cutoff.
- **Undated evidence.** TriviaQA's contamination is assumed from its 2017
  web provenance with no dated study, so as-of scoring ignores it.
- **Cross-source agreement entirely.** Today's score sets can't establish
  what two evaluators would have said in 2024, so reproducibility falls
  back to the curated evaluator count.

`tests/test_backtest.py` pins each of these. They are the load-bearing part
of the exercise; the 8/8 means nothing without them.

---

## What it showed

### The retirement test

| rank | benchmark | actual | trust | models used |
|---:|---|---|---:|---:|
| 1 | GPQA Diamond | kept | 73.9 | 33 |
| 2 | MATH Level 5 | kept | 71.6 | 29 |
| 3 | BIG-Bench Hard | kept | 63.5 | 81 |
| 4 | MMLU-Pro | kept | 53.2 | 608 |
| 5 | MMLU | **retired** | 45.0 | 172 |
| 6 | ARC | **retired** | 42.3 | 121 |
| 7 | TruthfulQA | **retired** | 36.8 | 7,095 |
| 8 | HellaSwag | **retired** | 28.2 | 97 |

|  | HF retired | HF kept |
|---|---:|---:|
| **scorer: retire** | 4 | 0 |
| **scorer: keep** | 0 | 4 |

Perfect separation: the worst replacement (53.2) beats the best retired
benchmark (45.0) by 8.2 points.

### The trajectory test

The 2024 replacements were chosen *because* they were harder. Two years on,
does the scorer say they aged?

| benchmark | Jun 2024 | today | change | measured saturation now |
|---|---:|---:|---:|---:|
| MMLU-Pro | 53.2 | 41.4 | −11.8 | 37% |
| BIG-Bench Hard | 63.5 | 26.7 | −36.8 | 48% |
| GPQA Diamond | 73.9 | 23.7 | −50.2 | 89% |
| MATH Level 5 | 71.6 | 18.9 | −52.7 | 94% |

All four declined, GPQA and MATH by more than 50 points. The benchmarks
selected to fix saturation are now scored as saturated themselves — which
is the pattern the project exists to surface, observed over time rather
than asserted.

### Is one factor doing all the work?

The retired benchmarks are also the older ones, so a scorer that did
nothing but rank by age would look like it works. It doesn't:

| ranking by | correct | separated | gap |
|---|---:|---|---:|
| **discrimination alone** | **8/8** | **yes** | +1.8 |
| freshness alone | 6/8 | no | −6.3 |
| specificity alone | 6/8 | no | −15.0 |
| reproducibility alone | 4/8 | no | −40.0 |
| **release date alone (no scoring)** | **6/8** | — | — |

**Discrimination — saturation measured from score distributions — is the
only factor that separates them alone**, and the trivial age-order baseline
fails. The result is not a restatement of "newer is better." The other
factors widen the margin from +1.8 to +8.2 but don't produce it.

### Sensitivity

The conclusion survives most weightings. Varying one weight from 0.1 to 0.6
while the others absorb the difference proportionally:

- **discrimination** (0.1–0.6): 8/8 throughout, gap +6.1 to +10.3
- **freshness** (0.1–0.6): 8/8 throughout, though the gap shrinks to +0.2
  at 0.1 — separation survives but only just
- **specificity** (0.1–0.6): 8/8 throughout, gap narrows to +0.7 at 0.6
- **reproducibility**: 8/8 up to 0.3, then **fails at 0.4 and above**
  (6/8, separation lost)

The reproducibility failure is explicable rather than alarming: at the
cutoff that factor is the curated evaluator count, and the *older*
benchmarks have more evaluators precisely because they had been around
longer. Weighted heavily, "well-covered" starts outvoting "still
discriminating." It argues against raising that weight, which is the only
actionable thing the sweep says.

---

## What changed as a result

**No weights were changed.** The test passed at the existing 40/20/20/20,
and adjusting them afterwards would have converted a prediction into a
retrofit.

One bug surfaced. A leakage test asserted that every retired benchmark is
flagged saturated today — and TruthfulQA wasn't, despite its own curation
notes recording the June 2024 retirement and a measured saturation of 87%.
The flag was corrected. It does not affect any score (the penalty only
applies to benchmarks with no score data, and TruthfulQA has 7,170), but the
catalog was internally contradictory and nobody had noticed by reading it.

---

## What this does not establish

**Eight benchmarks and one decision.** With four in each group, there are 70
possible splits; getting the right one by chance is about 1.4%. That is
suggestive, not conclusive, and it is one draw.

**The ground truth is a judgement, not a measurement.** Hugging Face retired
a set of benchmarks for stated reasons that included saturation, cost, and a
view about where the field should climb. Agreeing with that decision is
agreeing with a well-informed opinion.

**Only saturation is really under test.** Discrimination carries the result;
freshness, specificity and reproducibility are along for the ride, and one
of them actively hurts when weighted heavily. The other three factors remain
uncalibrated — this says nothing about whether 20/20/20 among them is right.

**The as-of reconstruction is imperfect.** The catalog's curated fields
(task specificity, evaluator counts) are recorded as of today and are not
time-varying, so the scorer knows 2026's view of how task-shaped a benchmark
is while pretending it is 2024. Only score distributions, release dates and
dated evidence are genuinely rewound.

**Two of the six retired benchmarks and two of the six replacements are
missing** from the catalog. Adding Winogrande, GSM8K, MuSR and IFEval would
make this a 12-point test, and is the cheapest way to strengthen it.

**A passing backtest cannot validate the weights.** It can only falsify
them, and it didn't. The honest reading is: *the scorer is not obviously
wrong about the one case where an expert judgement exists to check against.*

---

## If you want this to mean more

1. **Add the four missing benchmarks.** 12 points instead of 8, same test,
   no new machinery.
2. **Find a second dated decision.** Any leaderboard retiring or adding a
   benchmark with a stated reason is another draw. Two independent
   agreements would be considerably stronger than one.
3. **Make the curated fields time-varying** so the as-of reconstruction is
   honest about specificity and evaluator counts as well as scores.
4. **Test the other direction.** This checks that saturated benchmarks score
   low. Whether *high* scores predict anything useful — that a benchmark
   picked today still discriminates in two years — is the claim the tool
   actually makes, and it needs a forward test, not a backward one.
