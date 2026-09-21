# Methodology

How every number in this project is computed, and what evidence it had to
meet to get there. The goal is that you can disagree with a specific figure
and know exactly where it came from.

Conventions: scores are fractions internally (0–1) and shown as points
(0–100) in the UI. "Points" below always means percentage points of a
benchmark's usable score range.

---

## 1. Benchmark trust score

Four factors, each 0–1, combined by weight into 0–100, then reduced by
penalties. `benchmark_scoring.py`.

| factor | weight | what it asks |
|---|---:|---|
| discrimination | 0.40 | Does it still spread models out? |
| freshness | 0.20 | How long has the test set been public? |
| reproducibility | 0.20 | Do independent evaluators agree about it? |
| specificity | 0.20 | Does it map onto real work? |

**The weights are judgement calls.** See [BACKTEST.md](BACKTEST.md) for the
one empirical check on them, and its limits.

### discrimination — measured

From the score distribution. Take the top 10 models, and compute two things
against the usable range (ceiling minus random baseline):

- **spread** — how far the top 10 span
- **headroom used** — where that cluster sits within the range

```
tightness   = 1 - min(spread / 0.20, 1)
saturation  = min(1, 0.65 × tightness + 0.35 × headroom_used)
discrimination = 1 - saturation
```

Both terms are there because there are two ways to stop discriminating. A
benchmark everyone aces ranks models no better than one everyone fails
equally — proximity to the ceiling alone would miss the second case
entirely.

**Which population?** Sources cover different model populations and give
genuinely different answers: GPQA Diamond reads 89% saturated among Epoch's
frontier models and 59% among the HF leaderboard's open-community models.
The headline uses a frontier-tracking source where one exists
(`PRIMARY_SOURCE_PREFERENCE`), because "has this stopped separating the best
models?" is the usual question. Every source's reading is retained and shown.

Falls back to the curated `saturation_flagged` when no score data exists
(currently LiveCodeBench only), with `basis` set to `curated`.

### freshness — curated input, computed output

Exponential decay on the benchmark's age, halving every **730 days**. The
half-life is a judgement call: long enough not to punish a recent benchmark,
short enough that a 2018 multiple-choice set scores near zero.

Age is discounted by how the test set resists leaking:

| `holdout` | discount | meaning |
|---|---:|---|
| `public_static` | 1.00 | published once, public ever since |
| `partial_holdout` | 0.60 | questions public, grading material withheld |
| `refreshed` | 0.35 | new items added on a rolling basis |
| `private_holdout` | 0.00 | answers withheld; floor of 0.9 applied |

`partial_holdout` sits nearer "public" than "private" on purpose: hiding the
answer key blocks memorization, but the task text is still crawlable and
discussable. Unrecognized values decay fully, so a typo can't earn a
discount.

### reproducibility — measured where possible

For benchmarks with two comparable sources, match models across them by name
(`model_matching.py`) and split the per-model differences into two
quantities that mean different things:

- **offset** — the median signed difference. A systematic gap is a
  *methodology* difference (shot count, harness, prompt format). It means a
  published number isn't interpretable without knowing who produced it.
- **scatter** — the median absolute deviation around that offset. This is
  irreproducibility proper.

```
reproducibility = 1 - min(scatter / 0.08, 1)
```

Scatter drives the factor; offset is reported alongside rather than folded
in, because a constant gap is a fact about two harnesses while scatter is a
fact about the benchmark.

**A comparison is refused, not approximated, when** the two sources use
different normalizations, or fewer than 10 models overlap. Both guards
matter: comparing a baseline-normalized column against a raw one once made
GPQA's median delta read 24.5 points when the true figure was 7.9.

Falls back to `independent_evaluators / 5`, capped at 1.0, with `basis` set
to `curated` and an explanation naming why the measurement was unavailable.

### specificity — judgement

A 0–1 hand-assigned estimate of how narrowly a benchmark maps to real work.
1.0 is "resolve this GitHub issue"; 0.2 is "answer multiple-choice questions
across 57 subjects". Every value is argued in that benchmark's
`curation_notes`. This is the least defensible factor and it is 20% of the
score.

---

## 2. Penalties

Applied multiplicatively to the weighted score. These are defects that
undermine every factor at once, which is why they aren't factors themselves
— a benchmark can't compensate for a wrong answer key by being recent.

### Contamination

Two quantities, because they diverge:

- `contamination_rate` — fraction of items found in a pretraining corpus.
- `contamination_effect` — how far scores fall when the same models are
  re-evaluated on a decontaminated variant.

```
severity   = max(rate / 0.30, effect / 0.40), capped at 1
multiplier = 1 - (1 - 0.65) × severity
```

The worse of the two wins. HumanEval is why: a modest 13% overlap rate, but
scores fall 39.4% when decontaminated. Rate alone would have understated it
by a wide margin.

With the flag set but neither quantity known, the flat 0.65 applies.

**This is a known flaw, not a design choice.** 0.65 is also what
`severity = 1` produces, so *"contamination reported, nobody has measured
it"* is charged **exactly as hard as "measured to be maximally
contaminated"**. Ignorance gets the worst case. That contradicts the rule
this project applies everywhere else — `item_error_rate=None` means
unaudited and costs nothing, precisely so that absence of measurement is
not read as a finding.

It bites hardest on SWE-Bench Verified, whose contamination evidence
(OpenAI's report that frontier models reproduce gold patches verbatim) is
qualitative and therefore unquantifiable at present. Flagging it dropped
it from 40.7 to 26.4 and put it *below* HumanEval, whose contamination is
quantified and severe. `tests/test_scoring.py` pins both the inversion and
its cause.

Fixing it means choosing a penalty for "flagged, unmeasured" that sits
between 1.0 and 0.65 — a new free parameter, chosen with no evidence, on a
scorer that already has more parameters than validation. It is recorded
here rather than patched, and any fix should be decided on its own merits
rather than by what it does to the backtest.

### Item quality

```
severity   = min(item_error_rate / 0.20, 1)
multiplier = 1 - (1 - 0.60) × severity
```

`None` means **nobody has audited this benchmark** — not that it is clean.
An explicit `0.0` would mean a clean audit. The distinction is pinned by
tests because it is easy to erode.

`item_error_rate_basis` records what kind of number the rate is:
`"estimate"` (default — a measurement of the whole set, or a sample meant
to stand for it) or `"lower_bound"` (a floor the audit demonstrated, with
the remainder never examined). **It changes the wording, never the
score**: a floor of 16% renders as *"at least 16% of items are
mislabelled"* and an estimate of 16% as *"16% of items are mislabelled"*,
and both carry the identical penalty. Scoring a bound more harshly would
mean assigning a severity the evidence does not contain; the field marks
precision, which the four factors do not price. Only SWE-Bench Verified
is a `lower_bound` today.

### Reported saturation

A flat 0.80, applied **only** when there is no score data to measure
saturation directly. With data, the measurement already reflects it.

---

## 3. Evidence standard

Every curated claim carries its basis in `curation_notes`:

- **`RESEARCHED <date>`** — a specific source was found and cited, usually
  with a URL. All 22 entries currently meet this bar.
- **`CURATE(you)`** — evidence is missing, ambiguous, or the source's
  definition doesn't match the field. The note says what to look for.

Both can appear in one entry: an entry can be researched on contamination
and open on saturation.

Two tests enforce this. One fails if **any** entry lacks a researched basis;
another fails if any benchmark in the **top 5** does. Invented numbers
cannot lead the rankings without the suite objecting.

### `basis` values in the UI

| value | meaning |
|---|---|
| `measured` | computed from committed score distributions |
| `curated` | from a dated, cited claim in the catalog |
| `unknown` | no data and no claim; a neutral placeholder is used |

### Evidence dates

`evidence_dates` records when each claim became public, which is what makes
as-of scoring honest. Its most important job is preventing circularity: the
saturation flags on the benchmarks HF retired in June 2024 are *derived from
that retirement*, and dating them to the announcement keeps the backtest
from being handed its own answer.

A claim with no date is treated as unknown at any past date. Undatable
evidence can't be proven to have been available.

---

## 4. Model scoring

Downstream, in `scoring.py`. Two distinct trusts are in play and the code
keeps them apart:

- **benchmark trust** — how much to believe the *benchmark*, above.
- **source trust** — how much to believe the *report* of a model's result:
  independent source count, staleness of the report, and whether it is
  self-reported on the model's own card.

```
raw_score      = Σ(normalized_score × benchmark_trust) / Σ(benchmark_trust)
composite      = raw_score × source_trust
```

So 92% on HumanEval moves a model less than 40% on a benchmark that still
discriminates. Results from benchmarks not in the catalog get
`UNKNOWN_BENCHMARK_TRUST = 45` — middling on purpose, since an unrecognized
benchmark is not evidence of a bad one.

Ranking is **tiered** before scores are compared: models with confirmed
provenance rank above unconfirmed ones, corroborated above self-reported,
scored above unscored. A multiplier can't express "an unverified number is
not evidence"; a 95% self-reported score would still outrank a measured 60%
after any reasonable penalty.

---

## 5. What would change these numbers

Honest list of where the methodology is weakest:

1. **Specificity** is 20% of every score and is entirely judgement.
2. **Reproducibility** is measured for 4 of 22; the fallback proxy can
   contradict the measurement outright (GPQA).
3. **The saturation formula's constants** — 0.20 healthy spread, the 0.65/0.35
   split between tightness and headroom — are unvalidated.
4. **Penalty curves** — 0.30 full contamination rate, 0.20 full item error
   rate, and the floors — are set by looking at the benchmarks they separate,
   which is uncomfortably close to fitting to the sample.
5. **`item_error_rate` definitions vary by study.** SWE-Bench Verified
   records 0.10 (its creators' own estimate) while an independent audit
   found ≥59.4% of an examined subset had tests that reject correct
   solutions. Adopting that figure would roughly halve the score of the
   benchmark this catalog otherwise treats as a gold standard. Flagged in
   its entry as the most consequential open question here.
