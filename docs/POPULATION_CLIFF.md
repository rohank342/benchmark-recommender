# The population cliff — design only

**Nothing built.** All figures measured 2026-09-22.

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
