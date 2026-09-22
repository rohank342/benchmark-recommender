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

From the score distribution. Take the **top 20% of a stated population**
(minimum 30 models, else reported unmeasurable), and compute two things
against the usable range (ceiling minus random baseline):

- **spread** — how far the top 10 span
- **headroom used** — where that cluster sits within the range

```
tightness   = 1 - min(spread / 0.24, 1)
saturation  = min(1, 0.65 × tightness + 0.35 × headroom_used)
discrimination = 1 - saturation
```

Both terms are there because there are two ways to stop discriminating. A
benchmark everyone aces ranks models no better than one everyone fails
equally — proximity to the ceiling alone would miss the second case
entirely.

#### HEALTHY_SPREAD was derived on 2026-09-22, and never had been before

**It represents** the spread across the measured band at which a
benchmark separates its leaders beyond what measurement noise alone
would produce.

**The old 0.20 was chosen, not derived.** It entered in the pivot commit
with the comment "a spread this wide counts as fully discriminating" and
no basis. There is therefore no principled conversion from the top-10
era to the top-20% band; both had to be derived from scratch.

**The derivation** anchors on the only noise floor this repo measures —
cross-source scatter of the same model scored by two evaluators. Across
the 8 measurable benchmarks: median 0.0278, mean 0.0370, **max 0.0805**.
A band narrower than the scatter ranks noise, not models, so "fully
discriminating" sits several noise widths above that floor even for the
noisiest measurable benchmark: **3 × 0.0805 = 0.242, taken as 0.24.**

**The invented element, named:** the multiplier 3. No derivation escapes
one such choice; anchoring on the observed spread distribution instead
just relocates it to a quantile. The noise anchor is preferred because
it does not depend on which benchmarks happen to be catalogued.

**Every other parameter was checked the same way on 2026-09-22.** Seven
of nine reorder the catalog across their defensible range:

| parameter | range | rank moves (of 26) |
|---|---|---:|
| `HEALTHY_SPREAD` | 0.084–0.358 | **19** |
| `SATURATION_TOP_PERCENTILE` | 10–30% | **15** |
| `MIN_SATURATION_POPULATION` | 10–50 | **13** (3 tier changes) |
| `LEAKAGE_HALF_LIFE_DAYS` | 365–1460 | 8 |
| `FULL_CONTAMINATION_RATE` | 0.15–0.50 | 6 |
| `CONTAMINATION_PENALTY` | 0.50–0.80 | 5 |
| `SCATTER_TOLERANCE` | 0.04–0.16 | 5 |
| `ITEM_ERROR_PENALTY` | 0.40–0.80 | 3 |
| `FULL_ITEM_ERROR_RATE` | 0.10–0.40 | 3 |

Only the last two are close to inert. This is the ceiling on how much
any ranking here can mean, and it is reproduced in the README so a
reader of the ranking sees it.

**Sensitivity of HEALTHY_SPREAD itself — a finding, not a footnote.**
Defensible values run 0.084 to 0.358:

| HEALTHY_SPREAD | mean catalog health | benchmarks whose rank moves |
|---:|---:|---:|
| 0.084 (3× median scatter) | 58.8 | — |
| 0.139 (5× median scatter) | 56.3 | 17 |
| 0.200 (the old chosen value) | 53.5 | 20 |
| **0.240 (adopted)** | **51.3** | 19 |
| 0.282 (75th pct of spreads) | 48.9 | 20 |
| 0.358 (90th pct of spreads) | 45.5 | 19 |

**Mean health moves 13 points and about 20 of 26 benchmarks change rank
across the range.** The full-evidence tier's leader changes at 0.282
(Winogrande → BIG-Bench Hard). A constant whose plausible range reorders
the catalog is a real limit on how much any ranking here can mean.

*Coincidence worth recording: the median observed top-20% spread is
0.197, so the old 0.20 sits at the middle of a distribution it was never
derived from.*

**The percentile replaced a fixed top-10 on 2026-09-22.** Top-k of n asks
a different question at every n — top 10 of 33 models is the top 30%, top
10 of 4,575 is the top 0.2% — and that artifact moved readings by up to
0.81 with no change to the benchmark. 20% was chosen as the most stable
band at every minimum-population threshold tested. Full derivation and
the limits of the fix: [SATURATION_MEASUREMENT.md](SATURATION_MEASUREMENT.md).
**Absolute saturation levels are not comparable to anything this project
published before that date** — every reading fell, because a wider band
sees a wider spread.

**Which population?** Sources cover different model populations and give
genuinely different answers: GPQA Diamond reads 89% saturated among Epoch's
frontier models and 59% among the HF leaderboard's open-community models.
The headline uses a frontier-tracking source where one exists
(`PRIMARY_SOURCE_PREFERENCE`), because "has this stopped separating the best
models?" is the usual question. Every source's reading is retained and shown.

Falls back to the curated `saturation_flagged` when no score data exists
(currently LiveCodeBench only), with `basis` set to `curated`.

#### Diagnosis: why GPQA Diamond ranks below ARC

Analysis only, 2026-09-21. Nothing was changed. GPQA Diamond (2023,
PhD-written) scores **15.7**, last of 26, while ARC (2018, grade-school
multiple choice, retired by HF for saturation) scores **45.9**. That
ordering looks wrong, and the hypothesis under test was that it is the
population problem above rather than the specificity rubric.

**Verdict: the population problem is real and worth about 40% of the gap,
but it is not the main cause. The rubric is the smallest cause.**

| factor | GPQA | ARC | favours |
|---|---:|---:|---|
| reproducibility | 0.00 | 20.00 | **ARC +20.00** |
| discrimination | 4.23 | 18.88 | **ARC +14.65** |
| specificity | 4.00 | 6.00 | ARC +2.00 |
| freshness | 7.48 | 1.04 | GPQA +6.44 |
| **total** | **15.7** | **45.9** | **ARC +30.2** |

**1. Reproducibility is the biggest term, and it is perverse.** GPQA has
two comparable sources, so its reproducibility is *measured* — 29 shared
models, 8.1 points of unexplained scatter — and scores **0.000**. ARC also
has two sources, but v1 is length-normalized and Epoch is not, so the
comparison is refused and ARC falls back to its curated evaluator count of
5/5 = **1.000**.

> ARC gets full marks for reproducibility **because** its two sources
> cannot be compared. GPQA gets zero **because** its two sources can be
> compared and disagree. Being measurable costs 20 points.

This is the same class of error as the old contamination rule, where an
unquantified flag cost more than a measured one. It was fixed there and is
still live here.

**2. Discrimination, and the population problem.** GPQA's headline
saturation is 0.894 from Epoch's frontier models; on the v2
open-community leaderboard the same benchmark reads **0.588**. Reading
GPQA on the open-community population instead would add about **12.3
points** — roughly 40% of the total gap. ARC, by contrast, reads 0.528 on
Epoch and 0.527 on v1: it is population-insensitive, so none of its score
is a population artifact.

**A comparable-population measurement is not available for this pair.**
Both benchmarks nominally use `epoch_ai`, but matching model names across
the two score sets finds **4 shared models out of 269 and 76**. Epoch
evaluates GPQA on frontier models and ARC largely on older ones. "Same
source" is not the same population, and with 4 overlapping models a
like-for-like reading cannot be computed at all.

**3. Specificity contributes 2.00 points of 30.2.** The rubric is the
*smallest* factor in this gap. The intuition that "the rubric tanked
GPQA" is wrong — the rubric moved GPQA's specificity from 0.60 to 0.20,
which is 8 points of its trust score, but ARC's is only 0.30, so the
*difference* between them is small.

#### Other benchmarks read on mismatched populations

Every benchmark with two sources, sorted by disagreement:

| benchmark | spread | readings |
|---|---:|---|
| **MATH Level 5** | **0.431** | Epoch 0.938 (n=108) vs v2 0.507 (n=4,575) |
| **HellaSwag** | **0.383** | Epoch 0.524 (n=135) vs v1 0.907 (n=7,260) |
| **GPQA Diamond** | **0.306** | Epoch 0.894 (n=313) vs v2 0.588 (n=4,575) |
| MMLU | 0.090 | Epoch 0.817 vs v1 0.727 |
| GSM8K | 0.073 | Epoch 0.783 vs v1 0.856 |
| Winogrande | 0.066 | Epoch 0.641 vs v1 0.707 |
| BIG-Bench Hard | 0.017 | Epoch 0.483 vs v2 0.466 |
| ARC | 0.001 | Epoch 0.528 vs v1 0.527 |

**MATH Level 5 is the worst case and it sits in the backtest.** It ranks
first at the 2024 cutoff on a 0.938-vs-0.507 disagreement, and its
cutoff reading rests on 29 models. HellaSwag's spread is additionally not
even the same metric — v1 reports length-normalized accuracy.

Across the catalog, saturation is read on **four different populations**:
Epoch (20 benchmarks), v2 (3), v1 (1), EvalPlus (1). Any cross-benchmark
comparison mixes them, and the three benchmarks above show that mixing can
be worth 30–43 points of saturation. **The single-number ranking in the
UI and README is therefore not a like-for-like comparison**, and nothing
currently warns a reader of that.

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

**Since 2026-09-22 there is no fallback.** A health factor that cannot be
measured contributes **nothing**, and the remaining health factors are
renormalized to carry full weight — mirroring the contamination
treatment adopted the day before. The evaluator count is still computed
and shown, but it no longer enters the score.

Why: the curated fallback was *more generous* than the measurement it
stood in for (curated mean 0.580 against measured 0.485), so being
uncheckable paid better than being checked. Absence of measurement is
not a finding, in either direction.

**What it costs:** a benchmark with one evaluator and one with five now
score identically on this axis. That count is weak evidence, but it is
evidence, and this discards it.

**Freshness is deliberately exempt.** Its basis is `curated` because the
release date is curated, but it is computed exactly rather than proxied —
there is no measurement for it to be missing. Only `discrimination` and
`reproducibility` have a measurement path to fall off
(`FALLBACK_CAPABLE`).

**Because scores now rest on different numbers of factors, the UI says
which.** `BenchmarkTrust.evidence` reports factors used, how many were
measured versus curated, and which were dropped. Two scores of 70 are
not the same evidence if one averaged three factors and the other rests
on a release date — and the benchmarks scoring highest currently rest on
the *least*: MirrorCode's 90.5 is 2/3 factors, LiveCodeBench's 73.6 is
1/3, while GPQA Diamond's 14.6 is the only 3/3 with two measured.

#### Diagnosis: the fallback rewards being uncheckable

Analysis only, 2026-09-22. Nothing changed, and no treatment is picked here.

**This is the same bug class as the old flat contamination penalty**, which
was fixed on 2026-09-21. There, a flag nobody had measured cost as much as
the worst measured contamination. Here, a benchmark nobody *can* check
scores higher than one that was checked and failed.

> ARC scores **1.000** because its two sources cannot be compared. GPQA
> Diamond scores **0.000** because its two sources can be compared and
> disagree by 8.1 points. That one mechanism is 20 of the 30 points by
> which ARC outranks GPQA.

#### Who gets which, and what each group scores

| | n | mean | median | range |
|---|---:|---:|---:|---:|
| **measured** | 6 | **0.485** | 0.572 | 0.000 – 0.892 |
| **curated fallback** | 20 | **0.580** | 0.500 | 0.200 – 1.000 |

**The fallback is on average more generous than the measurement it stands
in for** (0.580 vs 0.485). It is not a neutral proxy; it is a bonus for
being unverifiable.

Four benchmarks receive the maximum 1.000 from the fallback:

| benchmark | why it isn't measured |
|---|---|
| **ARC** | two sources, but v1 reports length-normalized scores |
| **HellaSwag** | same |
| SWE-Bench Verified | only one source |
| HumanEval | only one source |

The first two are the sharp cases: a comparison *was* possible and was
refused on a correctness guard, and the refusal pays out at maximum.

#### What the guard is costing — measured

Lifting the normalization guard for these two (reporting the systematic
offset separately, which is what the offset/scatter split exists for)
gives real numbers:

| benchmark | overlap | offset | scatter | measured reproducibility | currently |
|---|---:|---:|---:|---:|---:|
| ARC | 40 models | −0.035 | 0.030 | **0.620** | 1.000 |
| HellaSwag | 36 models | −0.022 | 0.018 | **0.775** | 1.000 |

Both are far below the 1.000 the fallback awards. **Checked and rejected:
refetching a raw column is not an option** — the archived v1 leaderboard
publishes exactly one column per benchmark (`ARC`, `HellaSwag`, …) with no
raw/acc variant, so the data to make a like-for-like comparison does not
exist in that source.

#### Treatments

Effects on today's scores and on the backtest. **The backtest is affected
far more than the catalog**, because as-of scoring has no cross-source
data at all, so *all twelve* benchmarks there take the fallback.

| treatment | invents a parameter? | backtest | benchmarks moved |
|---|---|---|---|
| **(a) status quo** | no | 10/12, gap −17.3 | — |
| **(b) cap at measured mean (0.485)** | **yes** — the cap | 10/12, gap −7.8 | 10 |
| **(b′) cap at measured median (0.572)** | **yes** — the cap | 10/12, gap −9.4 | 10 |
| **(c) drop it, renormalize the rest** | **no** | 10/12, gap −8.7 | 20 |
| **(d) lift the normalization guard** | **no** | no change | 2 |

Largest movers under each:

**(b) cap at mean 0.485** — ARC 45.9 → 35.6, SWE-Bench Verified 41.3 →
34.4, HumanEval 30.6 → 23.9, TruthfulQA 28.5 → 22.2, HellaSwag 25.6 →
19.4. Only benchmarks above the cap move; everything at 0.400 or below is
untouched.

**(c) drop and renormalize** (0.40/0.20/0.20 → 0.50/0.25/0.25 for the 20
unmeasurable ones, per benchmark) — the widest change, and it moves scores
*up* as often as down: MirrorCode 76.3 → 90.4, GSO-Bench 74.8 → 83.5, The
Agent Company 73.3 → 81.6, while ARC 45.9 → 32.4, TruthfulQA 28.5 → 15.6,
TriviaQA 26.1 → 17.6. Benchmarks with strong measured discrimination gain;
benchmarks that were leaning on an unearned 1.000 lose.

**(d) lift the guard** — ARC's reproducibility 1.000 → 0.620 and
HellaSwag's 1.000 → 0.775, nothing else. No effect on the backtest, since
as-of scoring cannot use cross-source agreement either way.

#### What each treatment asserts

- **(a)** asserts that counting how many groups publish a number is a fair
  stand-in for whether those numbers agree. The measured-vs-curated means
  above are direct evidence against that.
- **(b)** asserts that the fallback should never exceed what measurement
  typically shows. It is the only treatment requiring a number nobody can
  source — mean or median of six values, which will move as the seventh
  measurement arrives. **This is the parameter-inventing option**, and it
  is the same shape as the half-severity option rejected for contamination.
- **(c)** asserts that an unmeasurable factor should not contribute at all,
  and that the remaining factors should carry full weight — mirroring
  contamination treatment (c), which was adopted. It invents nothing.
  Its cost is that a benchmark with one evaluator and one with five become
  indistinguishable, discarding information that, while weak, is real.
- **(d)** asserts that a systematic normalization difference is an
  *offset*, which the machinery already isolates, and should not void the
  scatter measurement. It invents nothing and is narrow. Its risk is real:
  length normalization is a per-item reweighting, not a constant shift, so
  part of the 0.030 and 0.018 scatter is the normalization itself — the
  resulting values are **lower bounds** on true reproducibility, not
  estimates. (b) and (d) are not mutually exclusive; nor are (c) and (d).

Not picked here. This is the owner's call.

### specificity — auditable judgement, NOT measurement

How narrowly a benchmark maps to real work, 0–1. 1.0 is "resolve this
GitHub issue"; 0.2 is "answer multiple-choice questions across 57
subjects".

Since 2026-09-21 this is **not a free-standing number**. Each benchmark
carries five rubric dimension scores of 0/1/2 — item provenance, output
and check, scope, who does this, scale — and specificity is computed as
their sum ÷ 10. See [SPECIFICITY_RUBRIC.md](SPECIFICITY_RUBRIC.md) (v2,
adopted by the owner). There is no default: an unscored benchmark raises
rather than quietly becoming 0.5.

**This is still judgement.** The rubric makes it decomposable, checkable,
and impossible to edit without editing a stated reason — it does not make
it measured, and it must not be described as measured. Five judgements
have replaced one.

**It has not been independently checked.** Both the pre-rubric values and
the rubric itself were written by Claude Code. A second reviewer scoring a
sample against the criteria is the validation, and that has not happened.
The rubric's own guidance is that differences below ~0.2 are noise — which
is roughly one reviewer disagreeing on two dimensions, and is enough to
flip the backtest's verdict (see [BACKTEST.md](BACKTEST.md)).

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

**With the flag set but neither quantity known, there is NO numeric
penalty.** The flag is surfaced as a warning in the penalty text and the
UI instead:

> WARNING: contamination reported but never quantified — no penalty applied

**Owner's decision, 2026-09-21 (treatment (c) in the diagnosis below).**
What it replaced was a flat 0.65, which is identical to what
`severity = 1` produces — so *"contamination reported, nobody measured
it"* was charged **exactly as hard as "measured to be maximally
contaminated"**. Ignorance got the worst case, and measuring bought
nothing: HumanEval's 13% rate and 39.4% effect land on 0.655 against an
unmeasured flag's 0.650.

The rejected alternative was half severity, which would have required
inventing a severity the evidence does not contain. This route keeps
unsourced numbers out of the scoring path and matches how
`item_error_rate=None` is already treated: absence of measurement is not
a finding.

**What it costs:** the scorer now understates real harm wherever the harm
is real but nobody has counted it. SWE-Bench Verified is the live
example — frontier models demonstrably reproduce its gold patches, and
that now costs it nothing. The warning has to carry that weight alone.

Nine benchmarks were affected; scores moved as follows (today):

| benchmark | before | after |
|---|---:|---:|
| SWE-Bench Verified | 26.9 | 41.3 |
| ARC | 29.9 | 45.9 |
| BIG-Bench Hard | 26.7 | 41.0 |
| Winogrande | 22.6 | 34.8 |
| MATH Level 5 | 18.9 | 29.1 |
| TruthfulQA | 18.5 | 28.5 |
| TriviaQA | 16.9 | 26.1 |
| HellaSwag | 16.6 | 25.6 |
| GSM8K | 14.4 | 22.1 |

As of 2024-06-01 only **GSM8K** changes (40.6 → 62.5): every other
flag either was not yet public at that date or had a measured rate by
then. A retired benchmark gaining 22 points at the backtest cutoff is
not a neutral change, and it was committed before the backtest was rerun.

It bit hardest on SWE-Bench Verified, whose contamination evidence
(OpenAI's report that frontier models reproduce gold patches verbatim) is
qualitative and therefore unquantifiable at present. Under the old rule
that flag dropped it from 40.7 to 26.4 and put it *below* HumanEval, whose
contamination is quantified and severe. `tests/test_scoring.py` now pins
the corrected behaviour: the flag warns, the score does not move, and a
*measured* rate still bites.

The options were: keep full severity, pick something between 1.0 and 0.65
(a new free parameter with no evidence behind it), or charge nothing and
warn. The owner chose the third on 2026-09-21. The diagnosis that informed
that choice follows.

#### Diagnosis: where the SWE-Bench / HumanEval inversion actually comes from

Analysis only. No value changed, and the three treatments below are
**hypothetical arithmetic, not proposals**.

**Before any penalty, SWE-Bench Verified is 16.75 points ahead.**

| factor | SWE-Bench Verified | HumanEval |
|---|---|---|
| discrimination (×0.40) | 0.297 → 11.86 *(measured)* | 0.286 → 11.46 *(measured)* |
| freshness (×0.20) | 0.482 → 9.64 | 0.164 → 3.29 |
| reproducibility (×0.20) | 1.000 → 20.00 *(curated)* | 1.000 → 20.00 *(curated)* |
| specificity (×0.20) | 0.950 → 19.00 | 0.450 → 9.00 |
| **weighted subtotal** | **60.50** | **43.74** |

The four factors say what you would expect: the 2024 benchmark of real
GitHub issues beats the 2021 benchmark of 164 toy functions, mostly on
freshness and specificity, with near-identical measured discrimination.
**The entire reversal happens in the penalty stage.**

| | SWE-Bench Verified | HumanEval |
|---|---|---|
| contamination multiplier | **0.650** — flat, flag only | **0.655** — severity 0.985 from a 13% rate and a 39.4% effect |
| item-quality multiplier | 0.672 — from the 0.164 floor | none recorded |
| combined | **0.4364** | **0.6552** |
| final | **26.4** | **28.7** |

Two things fall out of that table:

1. **A flag with no numbers attached (0.650) is charged fractionally
   harder than contamination measured at near-maximal severity (0.655).**
   HumanEval has one of the best-quantified contamination cases in the
   literature, and being measured buys it nothing.
2. SWE-Bench is the only benchmark here carrying **two** multiplicative
   penalties, and both derive from **one** audit of one non-random
   138-problem sample. They are independent defects with independent
   evidence, but not independent observations.

##### The three treatments, computed

Only the unquantified path changes. HumanEval's contamination is
quantified, so its 28.7 is identical in all three rows.

| treatment | contamination multiplier | SWE-Bench | HumanEval | gap | SWE rank |
|---|---:|---:|---:|---:|---|
| (a) full severity — *the old behaviour* | 0.650 | 26.4 | 28.7 | −2.2 | 18/26 |
| (b) half severity | 0.825 | 33.5 | 28.7 | +4.9 | 15/26 |
| **(c) warning only — ADOPTED 2026-09-21** | **1.000** | **40.7** | **28.7** | **+12.0** | **14/26** |

**How much of the gap comes from the full-severity charge? All of it.**
The flag costs SWE-Bench **14.2 points**; the inversion is 2.2 points
deep. Without the flag SWE-Bench leads by 12.0, and **half severity alone
is enough to restore the ordering** (+4.9). There is no reading of this
where the inversion is driven by anything else — not by the item-quality
floor, which is evidence-backed and applies in all three rows, and not by
the factors, which favour SWE-Bench by 16.75 before penalties.

##### What each treatment asserts, since that is the actual decision

- **(a)** asserts that a credible qualitative report of memorization is as
  damning as the worst measured contamination in the catalog. It is
  internally inconsistent with `item_error_rate=None` costing nothing, but
  it is the only option that never *under*-penalises.
- **(b)** asserts that unmeasured contamination is real but that its
  magnitude is unknown, so it should cost something without costing the
  maximum. It is the only option requiring a number nobody can source —
  0.5 is a placeholder, and the project's own standard says a number with
  no basis should not be in the scoring path.
- **(c)** asserts that a penalty needs a measurement, and that an
  unquantified flag belongs in the UI as a warning rather than in the
  arithmetic. It is the most consistent with the evidence standard and the
  most likely to understate real harm — SWE-Bench would sit at 40.7 with
  frontier models demonstrably able to reproduce its gold patches.

**The owner chose (c) on 2026-09-21.** The figures in this table were
computed before rubric v2 landed, so the absolute numbers have since
moved (SWE-Bench Verified is 41.3 today, not 40.7); the comparison
between treatments is unaffected.

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

1. **Specificity** is 20% of every score and is entirely judgement. It is
   now decomposed into five rubric dimensions per benchmark
   (docs/SPECIFICITY_RUBRIC.md v2), which makes it auditable and
   uneditable-without-a-reason. **That is not the same as measured**, and
   no second reviewer has scored anything against the rubric.
2. **Reproducibility** is measured for 6 of 26; the fallback proxy can
   contradict the measurement outright (GPQA). The backtest uses the proxy
   for all twelve, because as-of scoring has no cross-source data.
3. **The saturation formula's constants** — the healthy spread (0.24 since
   2026-09-22, derived from the measured noise floor; see below), the 0.65/0.35
   split between tightness and headroom — are unvalidated.
4. **Penalty curves** — 0.30 full contamination rate, 0.20 full item error
   rate, and the floors — are set by looking at the benchmarks they separate,
   which is uncomfortably close to fitting to the sample.
5. **`item_error_rate` definitions vary by study.** SWE-Bench Verified now
   records 0.164 as a `lower_bound` — OpenAI audited 27.6% of the set and
   found 59.4% of that subset materially flawed. The other 362 problems
   have never been examined, so the true rate is unbounded above. A
   separate 2026 preprint reports the opposite error (28.5% of a 49-task
   sample accept an incorrect patch), which a single rate cannot express.
6. **RESOLVED 2026-09-21.** An unquantified contamination flag used to be
   charged at full severity, which was the sole cause of SWE-Bench
   Verified scoring below HumanEval. The owner adopted treatment (c): the
   flag warns and carries no numeric penalty. The cost of that choice is
   that unmeasured-but-real contamination is now free.
7. **Specificity is rubric-based since 2026-09-21** — auditable judgement,
   NOT measurement, and not independently checked. See below.
