# What the backtest can and cannot establish

Analysis only. Nothing in the scorer changed as a result of this document,
and no value in the catalog was chosen with it in view.

The short version, stated first because it is the part that undercuts the
project:

> **Within these twelve benchmarks, age and measured saturation are
> uncorrelated (r = +0.01). Age predicts HF's retire/keep decision almost
> perfectly (r = +0.79). Saturation barely predicts it at all (r = +0.30,
> falling to +0.10 when measured with today's models).**
>
> The scorer's headline factor and the ground truth are close to
> independent. The trivial baseline and the ground truth are nearly the
> same variable. That is why sorting by release date ties four weighted
> factors, and it is a property of the test, not a bug in the arithmetic.

---

## 1. The twelve, with dates and both saturation readings

Saturation is measured from score distributions; `n` is how many models
were available to measure it. Scored as of 2024-06-01 and again today
(2026-09-21).

| benchmark | decision | released | age at cutoff | saturation 2024 | n | saturation today | n | trust 2024 | trust today |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| ARC | retired | 2018-03-14 | 6.2y | 0.626 | 121 | 0.528 | 142 | 42.3 | 29.2 |
| HellaSwag | retired | 2019-05-19 | 5.0y | 0.511 | 97 | 0.524 | 135 | 28.2 | 17.4 |
| Winogrande | retired | 2019-07-24 | 4.9y | 0.543 | 124 | 0.641 | 145 | 42.0 | 22.6 |
| MMLU | retired | 2020-09-07 | 3.7y | 0.612 | 172 | 0.817 | 249 | 45.0 | 18.6 |
| MATH Level 5 | **kept** | 2021-03-05 | 3.2y | **0.123** | 29 | **0.938** | 108 | 71.6 | 18.9 |
| TruthfulQA | retired | 2021-09-08 | 2.7y | 0.875 | 7,095 | 0.875 | 7,170 | 36.8 | 21.1 |
| GSM8K | retired | 2021-10-27 | 2.6y | 0.277 | 142 | 0.783 | 235 | 40.6 | 14.4 |
| BIG-Bench Hard | kept | 2022-10-17 | 1.6y | 0.247 | 81 | 0.483 | 92 | 63.5 | 26.7 |
| MuSR | kept | 2023-10-24 | 0.6y | 0.644 | 608 | 0.440 | 4,575 | 44.4 | 43.7 |
| IFEval | kept | 2023-11-14 | 0.5y | 0.717 | 608 | 0.814 | 4,575 | 48.9 | 35.9 |
| GPQA Diamond | kept | 2023-11-20 | 0.5y | 0.368 | 33 | 0.894 | 313 | 73.9 | 23.7 |
| MMLU-Pro | kept | 2024-06-03 | −0.0y | 0.594 | 608 | 0.374 | 4,575 | 53.2 | 41.4 |

Group means: retired benchmarks averaged 4.19 years old at the cutoff,
kept ones 1.09 years. Saturation 2024: retired 0.574, kept 0.449 — heavily
overlapping ranges (0.277–0.875 against 0.123–0.717).

### Correlations, computed

| relationship | Pearson r | Spearman ρ | n |
|---|---:|---:|---:|
| age vs saturation @ 2024-06-01 | **+0.010** (r² = 0.000) | −0.028 | 12 |
| age vs saturation today | **+0.017** (r² = 0.000) | +0.112 | 12 |
| age vs retired (0/1) | **+0.793** | | 12 |
| saturation @2024 vs retired | +0.300 | | 12 |
| saturation today vs retired | +0.098 | | 12 |

**Age and saturation are not the same signal here — they are barely
related at all.** That result cuts two ways and both matter:

- *Against the obvious worry.* Measured saturation is not a laundered
  proxy for age. The two carry different information, so the scorer is not
  merely age in disguise.
- *Against the project.* The ground truth being tested is almost entirely
  an age ordering. A scorer weighted 40% toward a variable that is
  uncorrelated with age is being graded on a test whose answer key is age.

Two readings of the zero correlation, and the data does not separate them:
either benchmark saturation genuinely does not track calendar age (a
finding), or saturation as measured here is too noisy at these sample
sizes to correlate with anything (a measurement problem). The `n` column
argues for taking the second seriously: MATH Level 5's 2024 reading rests
on 29 models and GPQA's on 33.

### The reading that should worry a reader most

MATH Level 5 goes from **0.123 saturated in June 2024 to 0.938 today**;
GPQA Diamond from 0.368 to 0.894. Some of that is real — those benchmarks
did get solved. But the model population also changed from tens of models
to hundreds, and from "whoever had submitted by mid-2024" to today's
field. **Saturation measured on 29 models and saturation measured on 108
are not the same quantity**, and this document cannot tell you how much of
the change is the field improving versus the sample filling in.

Note also that the trust column falls for **every single benchmark**,
kept and retired alike — the largest drops belong to two benchmarks HF
*kept* (GPQA −50.2, MATH −52.7). Whatever the scorer is tracking over
time, it is not "HF chose well".

---

## 2. Could any split of these twelve show that discrimination adds
information beyond age?

Yes, and it is possible to say exactly how much, because the question has
a finite answer at this size. There are 6 × 6 = 36 retired-versus-kept
pairs. For each, ask whether the ordering is right.

| ranked by | pairs correct |
|---|---:|
| release date (older = retire) | 34/36 (94%) |
| **full trust score** | **35/36 (97%)** |
| measured saturation alone | 22/36 (61%) |

Then the decisive cross-tab:

- **Age gets exactly 2 of 36 pairs wrong. Saturation gets both right.**
  Both are MATH Level 5 (kept, 3.2 years old) against TruthfulQA and
  GSM8K (retired, 2.6–2.7 years old). Age says the younger ones should
  survive; saturation says MATH was at 0.123 while TruthfulQA was at
  0.875, and saturation is right.
- **Saturation gets 14 of 36 pairs wrong. Age rescues all 14.**

So the incremental contribution of measured saturation over age, on this
test, is **two pairs — both involving one benchmark**. That is the whole
of it. It is a real answer to "does discrimination add anything beyond
age?" and the answer is "yes, 2/36, resting on a single benchmark whose
2024 saturation was measured across 29 models."

At the split level (top six versus bottom six) that advantage vanishes
entirely: both age and the full scorer land 10/12, because the one pair
the scorer gets wrong — MMLU over MuSR — happens to straddle the split
while the two it gets right do not.

**What this means for any future split of these twelve:** no re-slicing
rescues the test. The information is not hiding in a subgroup; there are
only two discordant pairs in the entire matrix, and both come from one
benchmark. Dropping MATH Level 5 would leave the scorer with *no*
demonstrable advantage over release date at all. Twelve points cannot
support a claim about incremental validity when the increment is n = 2.

### Three things that would make the existing test stronger without new events

1. **Time-vary the curated fields.** Specificity and evaluator counts are
   recorded as of today and reused for 2024. The scorer is time-travelling
   with 2026's opinions.
2. **Fix the reproducibility fallback.** As-of scoring cannot use
   cross-source agreement, so all twelve fall back to curated counts.
   GSM8K gets 1.0 at the cutoff from an unsourced count of 5, while
   today's measurement says 0.134.
3. **Report the pair matrix, not just the split.** 35/36 versus 34/36 is a
   more honest and more sensitive summary than 10/12 versus 10/12, in both
   directions — it shows the scorer edging ahead, and it shows the edge is
   two pairs wide.

---

## 3. What a useful second test needs, and real candidates

The existing test has one structural flaw that no amount of care fixes:
**every retired benchmark is old and every kept one is new.** Age and the
label are confounded by construction, so the test cannot distinguish a
saturation-detector from a calendar.

A second test is only worth building if it breaks that confound. In
practice that means finding dated decisions containing at least one of:

- **old but still discriminating** — kept, or never retired, despite age;
- **new but saturated** — retired or abandoned quickly.

Candidates below are real, dated, and sourced. **None are implemented, and
none informed any value in the catalog.**

### Candidates that break the confound

**ARC-AGI-1 — old but still discriminating (the strongest case).**
Released 2019; frontier models sat around 5% as late as 2024, and it was
only broken by o3 in December 2024. Roughly five years old *and*
undefeated — the exact cell the current test has zero examples of. The
ARC Prize published dated analyses throughout.
→ https://arcprize.org/blog/oai-o3-pub-breakthrough (2024-12-20)

**SWE-bench Verified — new but abandoned.** Released 2024-08-13, and
OpenAI published its reasons for no longer evaluating on it on
2026-02-23: roughly 18 months. Already in this catalog with dated
evidence, so no new curation is needed to use it.
→ https://openai.com/index/why-we-no-longer-evaluate-swe-bench-verified/

**GPQA Diamond and IFEval — new but saturated.** Both released late 2023,
both *kept* by HF in June 2024, and both measured here at 0.894 and 0.814
saturation today. They are already in the catalog and already provide
"new and saturated" data points — for a *forward* test, not this one.

### Dated retire/replace decisions from other organisations

**Aider: original code-editing benchmark → polyglot, 2024-12-21.** The
clearest analogue of the HF event, from a different org, with saturation
stated explicitly as the reason: the top score had reached 84.2% (112 of
133 exercises), and new leaders were separated by one or two problems.
One retire/replace pair, so one draw — but an independent one.
→ https://aider.chat/2024/12/21/polyglot.html

**Artificial Analysis Intelligence Index v4.0, 2026-01-06.** Replaced
several popular benchmarks with "real-world" evaluations, citing
saturation directly: top models scored 73 on v3.0 and ≤50 on v4.0. Their
changelog carries dated component lists across versions, which would
yield *multiple* dated add/drop decisions rather than one — the most
promising source on this list for volume.
→ https://artificialanalysis.ai/changelog
→ https://venturebeat.com/technology/artificial-analysis-overhauls-its-ai-intelligence-index-replacing-popular

**ARC-AGI-1 → ARC-AGI-2, 2025-03-24.** A dated replacement announced
directly in response to o3 saturating the original.
→ https://arcprize.org/blog/announcing-arc-agi-2-and-arc-prize-2025

**GLUE → SuperGLUE, 2019-05-02.** The canonical case: GLUE saturated
within a year of release and its authors built the replacement. Predates
this catalog's era and the score data needed to measure it, but it is a
clean, well-documented retire/replace with a stated saturation reason.
→ https://arxiv.org/abs/1905.00537

**HF Open LLM Leaderboard v2 retirement, 2025-03-13.** Announced by
clefourrier, with the reasons given as benchmarks failing to follow
changing model capabilities and the risk of encouraging "hill climbing
irrelevant directions". Useful as a *dated obsolescence marker for the
v2 six* — but it retires all six at once, so it yields no retained/dropped
split and cannot be scored the way the June 2024 event is.
→ https://huggingface.co/spaces/open-llm-leaderboard/open_llm_leaderboard/discussions/1135

### What to check before building any of these

1. **Is there per-model score data for the retired side, dated?** Without
   it there is no measured saturation, and the test degrades to comparing
   curated judgements. This is the binding constraint — it is what makes
   the aider and AA events harder to use than they look.
2. **Was the stated reason saturation, or cost, or fashion?** HF's 2024
   decision mixed saturation with cost and a view about where the field
   should go. A second test inherits whatever its ground truth actually
   encodes.
3. **Does it break the age/label confound?** If the retired set is simply
   older again, the second test adds sample size without adding power, and
   the age baseline will tie the scorer there too.

Criterion 3 is the one that matters. Another twelve benchmarks arranged
old-retired and new-kept would be a bigger version of the same
uninformative test.
