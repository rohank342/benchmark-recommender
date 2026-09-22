# Proposal: split the trust score in two

**Status: ADOPTED and IMPLEMENTED 2026-09-22.**

Adopted on the argument that measurement health and task relevance are
different questions — **not on any test result**. The exploratory re-runs
below predicted the backtest would get worse, and it did: **10/12 → 8/12**,
gap −17.3 → −20.6. That is the price of the change and it was known and
accepted before implementing.

### Open work this leaves behind

**Relevance is really a property of a (benchmark, task) PAIR, not of a
benchmark.** "Is this task-shaped?" only has an answer once you say which
task — SWE-Bench Verified is highly relevant if you are shipping patches
and irrelevant if you are picking a model to answer physics questions. A
single per-benchmark relevance score is therefore an **approximation**,
and the UI half-admits it by filtering to a task category before showing
the number.

Scoring relevance per (benchmark, task) pair would mean a rubric applied
per pairing rather than per benchmark, and a UI that recomputes it from
the user's task description rather than looking it up. **Flagged, not
solved.** It is recorded in `benchmark_scoring.RELEVANCE_FACTOR` as a
CURATE marker.

## The diagnosis this comes from

Every test this project has run asks whether a benchmark is still a
working **measurement**:

- **The HF backtest** asks whether HF retired the benchmarks that had
  stopped discriminating.
- **Candidate 1** asks whether a benchmark a lab abandoned was already
  failing as a measurement.

`task_specificity` answers a different question — whether a benchmark is
**relevant to a task you care about**. A benchmark can be a perfect
measurement of something you do not need, and a broken measurement of
something you do. Averaging those into one number means neither question
gets answered.

**The evidence that this is not just tidiness.** On Candidate 1 the
factor contributions to the gap were:

| factor | contribution |
|---|---:|
| discrimination | **+2.02** (correct direction) |
| reproducibility | 0.00 |
| freshness | −2.69 |
| **specificity** | **−16.00** |

The measured factor got the answer right. A 20%-weighted factor with no
measurement behind it overrode it roughly eight to one, and the scorer
failed a test it would otherwise have come close to passing.

The model side of this project already keeps two trusts apart for exactly
this reason — how much to believe a benchmark, versus how much to believe
a report of a model's result on it — because "a multiplier cannot express
*an unverified number is not evidence*". The same argument applies here:
a multiplier cannot express *this measurement works but may not be what
you want*.

## The proposal

**Two scores, never multiplied together.**

### 1. Measurement health (0–100)

`discrimination`, `freshness`, `reproducibility`, and all the penalties,
reweighted **proportionally** so they sum to 1:

| factor | now | under the split |
|---|---:|---:|
| discrimination | 0.40 | **0.50** |
| freshness | 0.20 | **0.25** |
| reproducibility | 0.20 | **0.25** |
| specificity | 0.20 | — |

0.40 / 0.80 = 0.50, 0.20 / 0.80 = 0.25. **Proportional so that no new
weight is chosen** — this project has more free parameters than
validation already, and inventing three new ones while removing a factor
would make the change unauditable.

Penalties stay on health, because contamination and a wrong answer key
are defects *of the measurement*.

### 2. Task relevance (0–100)

`task_specificity` from rubric v2, shown on its own. Not multiplied into
health, not averaged with it.

It is a **property of the pairing** between a benchmark and what the user
wants, which is why it does not belong in a single benchmark-level
number. The current design already half-admits this: the UI filters
benchmarks by task category *and then* re-uses a score that has task-fit
baked into it, applying the same judgement twice in different forms.

## Every consumer of `trust_score`, and what each would need

| consumer | use today | under the split |
|---|---|---|
| `app.py:135` benchmark table `trust` column | single number | two columns: `health`, `relevance`. Sort by health; relevance is a second axis, not a tiebreak |
| `app.py:148` "Most trustworthy for this task" | `max(trust_score)` | **needs a decision**: rank by health within a task category, or show the health leader and the relevance leader separately when they differ |
| `app.py:151` low-trust warning, `trust_score < 35` | flags weak benchmarks | threshold applies to **health only**. A benchmark can be a fine measurement of the wrong thing; that is not a warning, it is a filter |
| `app.py:182` detail panel header | `{trust:.1f}/100` | two headline numbers |
| `app.py:311,418` model tab | already a separate model-side trust | unchanged; the naming collision gets worse and the existing note explaining it needs expanding |
| `scoring.py:122` `_weighted_point` | weights each model result by `trust.trust_score` | **the substantive decision.** See below |
| `scoring.py:45` `UNKNOWN_BENCHMARK_TRUST = 45.0` | fallback for unrecognised benchmarks | needs a health-scale equivalent; 45.0 was picked against the combined scale |
| `backtest.py:89,162` | `Outcome.score`, trajectory table | would use health — see the exploratory section |
| `task_matcher.py:190` demo print | single number | cosmetic |
| `BenchmarkTrust.summary` / `dominant_factor` | "held back by X" over all four factors | must not report specificity as holding back a *measurement* |
| tests | ~25 assertions on `trust_score` | rewritten; the pinned backtest results change |

### The model-side decision

`scoring.py` weights each model result by the trust of the benchmark it
came from. Under the split it should weight by **health alone**:

- A model's HumanEval result should count less because HumanEval is a
  weak *measurement*, not because HumanEval is a poor match for the
  user's task — the task match was already applied when the category was
  chosen.
- Weighting by relevance would apply the task judgement twice, which is
  the bug described above.

This is a real behaviour change to model rankings and would need its own
before/after diff. It is not covered by the exploratory runs below.

## EXPLORATORY / POST-HOC — what the tests would show under health alone

**These re-runs cannot count as passes or as evidence for the split.**
The proposal is motivated by the structure of these very tests — it was
designed after seeing that specificity caused the Candidate 1 failure —
so re-running them is circular by construction. They are reported because
the alternative is proposing a change while hiding what it does.

### The HF backtest

| | current | health only |
|---|---|---|
| correct | **10/12** | **8/12** |
| separated | no | no |
| gap | −17.3 | −20.6 |

**It gets worse, as expected.** Discrimination alone was already 8/12, and
removing specificity moves the full scorer toward that. The expectation
stated up front — that this probably rescues nothing — holds.

Under health alone, ARC rises to 46.6 and IFEval falls to 44.8, so a
retired benchmark overtakes a kept one that specificity had been
protecting. The split does not fix the backtest; it trades one error for
another.

### Candidate 1

| | current | health only |
|---|---|---|
| SWE-Bench Verified (S) | 63.5 | 54.4 |
| GPQA Diamond (G) | 46.9 | 53.6 |
| G − S | −16.6 | **−0.8** |
| verdict | FAIL | **still FAIL** |

**The failure nearly disappears but does not.** Removing specificity
strips 15.8 of the 16.6-point error, which is what the Candidate 1
diagnosis predicted. What is left is a 0.8-point failure — inside any
reasonable noise band, but still on the wrong side, and a near-miss is
not a pass.

So: the split is well-motivated by the *diagnosis* and does **not**
rescue either test. Anyone adopting it should do so because the two
questions are genuinely different, not because it improves a result. It
does not.

## What this would change in the README's claims

The README's headline is a single comparison:

> For code generation, **HumanEval scores 30.6/100 and MirrorCode scores
> 76.3.**

Under the split that becomes two numbers each, and the claim has to be
restated. The honest version is *stronger*, because most of the
HumanEval–MirrorCode gap is measurement health rather than task fit:

- "HumanEval is a weaker measurement than MirrorCode" — supported by
  measured saturation, contamination and age.
- "HumanEval is less relevant to real coding work" — a rubric judgement,
  and currently silently folded into the same number.

Specific edits required:

1. **The headline pair** restated as health + relevance.
2. **"What you can and can't trust here"** — the judgement-calls section
   currently lists `task_specificity` alongside weights and thresholds.
   Under the split it becomes the *entire* second score, which is a much
   more prominent admission: **one of the two headline numbers is
   judgement end to end, unmeasured and unchecked by a second reviewer.**
3. **The limitations section** — "the weights are uncalibrated" would need
   to say the health weights are a proportional rescaling of uncalibrated
   weights, so they inherit the same problem and add no new one.
4. **The backtest paragraph** — must state that the split makes the
   backtest *worse* (8/12), or it would read as an improvement.

## Tradeoffs, including the reasons not to do it

**For:**
- The two questions are different and the project's own tests only ever
  probe one of them.
- It removes the mechanism by which an unmeasured factor overrode a
  measured one on Candidate 1.
- Every number in health is measured or penalty-driven; relevance is
  openly judgement. The measured/curated/judgement boundary the README
  leads with becomes structural instead of a table.
- No new free parameters.

**Against:**
- **It makes the only two tests worse or no better.** 10/12 → 8/12, and
  Candidate 1 still fails.
- **Two numbers are harder to act on than one.** "Which benchmark should I
  believe?" is the question the project exists to answer, and the answer
  becomes "it depends which axis you care about".
- **Relevance is a property of a pairing, not of a benchmark**, so showing
  it as a per-benchmark score is still not quite right. A correct version
  would score relevance per (benchmark, task) pair, which is a bigger
  change than this proposal.
- **It is a large refactor** — ~25 test assertions, the model-scoring
  path, the UI, and three docs — for a change that improves no measured
  outcome.
- **Motivated reasoning risk.** This was designed after specificity caused
  a test failure. That is a legitimate way to notice a design flaw and
  also exactly how post-hoc rationalisation looks. The exploratory runs
  are the check on it, and they do not support the change on performance
  grounds.

## Recommendation

Adopt it only on the argument that the two questions are different —
which I think is correct and is supported by the model side already doing
this. **Do not adopt it expecting better test results.** If the decision
rests on the tests, the answer is no.
