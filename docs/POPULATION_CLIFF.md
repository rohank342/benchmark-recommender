# The population threshold — a plateau, not a cliff

**Nothing built, and nothing needs building.** Figures measured
2026-09-22 and re-measured 2026-09-23.

## SUPERSEDED IN PART BY D6, 2026-09-24

**The plateau narrowed and the threshold is now on its edge.** D6
measures saturation over distinct models and drops the 188 rows that
name no model, which shrinks several populations:

| counted by | plateau | headroom above 30 |
|---|---|---:|
| rows *(what the section below measured)* | 17–35 | 5 |
| **models, under D6** | **15–30** | **0** |

At a threshold of 31, **FrontierCode (30 models) falls out**. SWE-Bench
Verified is at 33, GSO-Bench at 38. And **OSWorld has already crossed**:
37 of its 57 rows were agent-only submissions, leaving 9 models, so it
is now `thin` rather than `partial`.

**So the conclusion below — "a cliff with nothing standing on it does
not need a fence" — no longer holds as stated.** Something is standing
on it. The redesign options at the end of this document (graded
confidence, subsampling intervals) move from "not warranted" to
"warranted if another benchmark approaches the line". They are still
unbuilt, and this project is in a resting state, so they go to
`CLAUDE.md` §8 rather than being built now.

The caveat the section below raised against itself — that its counts
were rows, not models — turned out to be the thing that mattered.

---

## Conclusion first, revised 2026-09-23 — SUPERSEDED, see above

This document was originally titled "the population cliff" and argued
that a hard cutoff was a design problem. **Measured more finely, it is
not.** `MIN_SATURATION_POPULATION` can be set anywhere from **17 to 35
inclusive** without changing a single rank, tier or health score in the
catalog:

| threshold | rank moves | tier changes | mean health |
|---:|---:|---:|---:|
| 10–16 | 9 | 1 | 49.0 |
| **17–35 — the plateau** | **0** | **0** | **49.2** |
| 36–38 | 10 | 2 | 50.9 |
| 39+ | 13 | 3 | 51.0 |

*(`python probes/impact.py parameter MIN_SATURATION_POPULATION 10 15 16
17 20 25 30 34 35 36 38 39 40 45`)*

The current value of 30 sits **inside a 19-wide plateau**, 13 above its
lower edge and 5 below its upper one. The mechanism is still a cliff —
crossing the threshold removes a factor and moves a benchmark to another
evidence tier, it does not degrade a score gradually — but **no
benchmark is near enough for the mechanism to bite**, so the redesigns
sketched below are not warranted. Revisit if, and only if, the watch
list moves.

**No redesign is needed while benchmarks stay clear of the plateau's
edges.** The graded-confidence and subsampling-interval options at the
end of this document remain written up, and remain unbuilt.

## The watch list — three benchmarks, 5 to 8 models above the line

These are the ones to watch, because they are what would end the
plateau. Each would become unmeasurable and drop to `thin` if its score
source lost a handful of models:

| benchmark | models | margin above 30 |
|---|---:|---:|
| **SWE-Bench Verified** | 35 | 5 |
| **FrontierCode** | 35 | 5 |
| **GSO-Bench** | 38 | 8 |

Populations grow far more often than they shrink, so the realistic
trigger is not a benchmark losing models — it is **the threshold being
raised, or the way models are counted being changed.** The second of
those is live: see the caveat below.

## A caveat that undercuts this whole document

The counts above are **rows, not models**. `probes/config_rows.py`
(2026-09-23) found that 9 of 20 Epoch exports hold more rows than
distinct models, because a configuration column — `Agent`, `Edit
format`, `Shots` — separates several runs of the same model.

**OSWorld is the case that matters here.** It appears below with 57–58
models and therefore comfortably clear of the threshold. It has **10
distinct models**. If the catalog ever counts models rather than rows,
OSWorld drops below the minimum immediately, and the "nothing sits
between 16 and 35" claim that makes this a plateau has to be recomputed
on the corrected counts.

So the plateau is real **under the current definition of a population**,
and that definition is itself an open question. This document does not
resolve it; D6 later did, see CLAUDE.md section 8 item 4 and
`docs/CONFIG_ROWS.md`.

## Where the 30 came from — derived, not chosen

**Derived**, from the stability table in
`docs/SATURATION_MEASUREMENT.md`: across 20 cohort-versus-full-population
pairs, mean |Δ| for the top-20% band falls 0.076 → 0.057 from a minimum
of 10 to a minimum of 30, then flattens (0.052 at 50, 0.056 at 100). The
largest improvement step is 10 → 30 and there is little to buy after it.

That is a weaker kind of derivation than `HEALTHY_SPREAD`'s — it picks
the knee of a curve rather than anchoring on a measured quantity — but
it is a basis in the data, not a preference. It is recorded here because
"derived or chosen" is exactly the question that went unasked about
`UNKNOWN_BENCHMARK_TRUST` and `HEALTHY_SPREAD` for months.

---

## Original framing, kept for the record

`MIN_SATURATION_POPULATION = 30` is a hard cutoff: at 30 models a
benchmark's saturation is measured and it can reach the FULL or PARTIAL
evidence tier; at 29 it is unmeasurable, drops to THIN, and stops being
comparable with anything above it. A benchmark gaining or losing a
handful of evaluations can cross that line.

## Quantified — and the first finding corrects an earlier claim

**Population size of every benchmark near the threshold:**

| benchmark | models in its largest score set |
|---|---:|
| The Agent Company | **16** |
| SWE-Bench Verified | **35** |
| FrontierCode | **35** |
| GSO-Bench | **38** |
| Humanity's Last Exam | 51 |
| OSWorld | 57 |

**Nothing sits between 16 and 35.** So at ±5 the cliff bites nothing:

| threshold | full | partial | thin | benchmarks changing tier |
|---:|---:|---:|---:|---|
| 10 | 8 | 16 | 4 | The Agent Company gains |
| 20 | 8 | 15 | 5 | — |
| 25 | 8 | 15 | 5 | — |
| **30 (current)** | **8** | **15** | **5** | — |
| 35 | 8 | 15 | 5 | — |
| 40 | 8 | 12 | 8 | FrontierCode, GSO-Bench, SWE-Bench Verified fall |
| 50 | 8 | 12 | 8 | same three |
| 60 | 8 | 10 | 10 | + HLE, OSWorld |

**Correction to an earlier report.** A previous session stated that
"three of the four most rank-unstable benchmarks sit within a few models
of the threshold". Re-measured: they sit **5 to 8 models above it**
(35, 35, 38), and the threshold would have to move to **40** before any
of them changes tier. The instability that appeared in the rank-range
analysis came from testing the threshold at **50**, not from proximity to
30. The cliff is real; the catalog is currently sitting in a flat part of
it.

That flatness is luck, not design. Three benchmarks sit 5 models above
the line, and any of them gaining evaluations is fine while any of them
being *re-measured on a smaller set* would flip it.

## Where did 30 come from?

**Derived, but coarsely.** It came from the stability table in
[SATURATION_MEASUREMENT.md](SATURATION_MEASUREMENT.md), which tested
minimum populations of 10, 30, 50 and 100 and found the largest
improvement between 10 and 30, flattening after. So the *value* is
data-derived — unlike `HEALTHY_SPREAD`, which was chosen — but the
**grid was 10/30/50/100**, so "30" is really "somewhere between 10 and
50, rounded to the grid point tested".

Nothing was measured at 25, 35 or 40 when the threshold was set. The
table above is the first time those were run.

## Options

### (1) Keep the cliff, re-derive the value on a finer grid

**Invents:** nothing new; refines an existing derivation.
**Changes:** possibly nothing — the flat region from 20 to 35 means any
value in that range gives today's catalog. Which is itself the argument
that the current value is not doing much work.
**Cost:** cheap. **Leaves:** the cliff, so a benchmark can still flip
tier on one evaluation.

### (2) Graded confidence instead of a cliff

Replace the boolean with a confidence that rises with population size,
and let the tier follow the confidence.

**Invents:** the shape of the curve and where the tier boundaries sit —
two or three new free parameters, in a project that already has seven
whose ranges reorder the catalog.
**Changes:** everything near the boundary becomes a judgement about
curve shape rather than a count.
**Verdict:** hard to justify under this project's own standards. It
replaces one arbitrary number with several.

### (3) Subsample for an uncertainty interval, and let the interval decide

Bootstrap the saturation reading: resample the population with
replacement, recompute the top-20% statistic, report a confidence
interval. A benchmark whose interval is wider than some width is not
measurable; below that, it is.

**Invents:** the interval width that counts as "measurable" — one
parameter, replacing one parameter.
**Changes:** the decision stops being about *how many models* and starts
being about *how much the answer moves*, which is the thing actually at
stake. A 30-model population with tightly clustered scores would be
measurable; a 60-model population with a fat tail might not be.
**Cost:** moderate — a bootstrap over each score set, cheap at these
sizes.
**This is the only option that measures the quantity the cliff is a
proxy for.** The count is a stand-in for "is this estimate stable?", and
a bootstrap answers that directly.

**It would also produce something the project currently lacks: an error
bar on saturation.** Every saturation figure is reported to three
decimal places with no uncertainty attached, and
[RANK_RANGES.md](RANK_RANGES.md) already shows the ranking cannot
support that precision.

## What is not recommended here

No option is picked. But the analysis has one asymmetry worth stating:
**(2) adds parameters to a project whose main published caveat is that
seven parameters already reorder its catalog**, while (3) replaces a
count with a measurement of the thing the count approximates. If the
owner wants the cliff gone rather than moved, (3) is the one that trades
an arbitrary threshold for an empirical one.
