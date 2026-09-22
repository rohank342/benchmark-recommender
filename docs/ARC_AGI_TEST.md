# ARC-AGI-1 as an old-but-unsaturated test — scoped, and NOT recommended

**Design only. Nothing built, no fetcher written, no score computed.**

**Verdict up front: do not build it.** The score data exists and is
good, but it is concentrated *after* the window the test needs. The
minimum pair count cannot be met at any usable as-of date. Killing it
here costs an afternoon; building it first would have cost a week.

---

## Why it was worth scoping

ARC-AGI-1 is the only identified benchmark that occupies the cell the
retired backtest does not contain: **old and still discriminating.**
Released 2019; frontier models sat around 5% into 2024; first broken by
o3 in December 2024. For roughly five years it was old *and* unsolved,
which is exactly the case where measured saturation and a calendar
predict opposite things.

With the backtest [retired for lack of power](BACKTEST.md), a test that
could actually discriminate is worth more, not less.

---

## What a catalog entry would require

| requirement | status |
|---|---|
| **Score source** | `arcprize/arc_agi_v1_public_eval` on HF — **76 model directories × ~400 per-task JSON files.** Rich, and far above the 30-model minimum in aggregate. |
| **Dated model population** | **Not provided.** Directory names are model names (`gpt-4o`, `claude-opus-4-8-high`); no evaluation dates and no release dates. Dates would have to be matched externally, which is the name-matching problem that has already produced four bug classes here. |
| **Verified vs self-reported separable?** | **Only partially.** ARC Prize verifies semi-private results and marks public-set results as self-reported. This dataset is the **public eval** set — i.e. the self-reported population. The verified population is on the leaderboard, which is JS-rendered and publishes no data file this repo could find. **The two populations cannot currently be kept separate in-repo, and mixing them would violate the project's own two-trusts rule.** |
| **Release date / metadata** | 2019-11-05, Chollet, arXiv 1911.01547. Straightforward. |
| **Holdout type** | Needs a real decision: the public eval set is `public_static`, the semi-private set is closer to `private_holdout`. Scoring the public set and labelling it held-out would be wrong. |

### Which of the four bug classes this source is vulnerable to

1. **Uncheckability payout** — yes, latently: one source only, so
   reproducibility would be unmeasurable and dropped, putting ARC-AGI-1
   in the **PARTIAL or THIN tier** depending on whether saturation is
   measurable.
2. **Unquantified flags at full severity** — not applicable; nothing to
   flag yet.
3. **One field, two quantities** — **yes, acutely.** Public-set and
   semi-private scores are different quantities and would land in the
   same field unless kept apart. This is the `contamination_effect`
   error waiting to happen.
4. **Top-k / population artifacts** — **yes.** 72 of 76 models are 2025
   or later, so the population is overwhelmingly post-breakthrough. Any
   percentile over it measures the modern frontier, not the 2019–2024
   era the test is about.

---

## The test, pre-registered (so it cannot be designed after the data)

Registered even though the recommendation is not to build it, so that a
later session cannot build it *and* choose the criteria afterwards.

- **Prediction:** at an as-of date inside the unsaturated window,
  ARC-AGI-1 has **high measured discrimination** despite being the
  **oldest** benchmark in the comparison set. The age baseline predicts
  the opposite.
- **As-of date:** **2024-06-01**, matching the existing cutoff and
  sitting six months before o3. A fallback of 2024-11-01 is permitted
  *only* if stated before scores are read.
- **Comparators:** the 12 benchmarks already scored at that cutoff, **in
  the same evidence tier** — cross-tier pairs are void.
- **Leakage gate (blocking):** no ARC-AGI evidence dated on or after the
  as-of date may be visible; specifically nothing derived from the
  December 2024 o3 result or the March 2025 ARC-AGI-2 launch. If any
  is, the run is void.
- **Pass criterion:** the scorer is right on **≥ 70%** of discordant
  pairs, with **at least 10 discordant pairs.**
- **Age baseline, fixed now:** rank by release date, newest first,
  within tier. ARC-AGI-1 is the oldest, so the baseline predicts it is
  the most saturated. Scored on the same pairs, reported alongside
  every time.
- **Underpowered clause:** if fewer than 10 discordant pairs exist, the
  report is **"underpowered — no verdict"**, never a result. This is the
  lesson of Candidate 1 (1 pair) and the hindcast (4 pairs), both of
  which produced numbers that meant nothing.
- **Evidence against the scorer:** ≤40% of discordant pairs; or the age
  baseline matching it; or a verdict that flips when ARC-AGI-1 itself is
  dropped.

---

## Why it fails feasibility

**Checked by listing the dataset's model directories — no scores were
read and no outcome computed.**

| era (from model family names) | models |
|---|---:|
| ≤ 2024-06 | **2** (`gpt-4o`, `claude-3-haiku`) |
| 2024-07 – 2024-12 | 2 |
| ≥ 2025 | **72** |

**The minimum population for a saturation reading is 30.** At the
registered as-of date of 2024-06-01 there are **2** candidate models. At
the fallback of 2024-11-01 there are about **4**. The window the test
needs closes in December 2024, when o3 broke the benchmark — and 95% of
the available data is from after it closed.

So ARC-AGI-1 at a 2024 as-of date would be **THIN tier**: discrimination
unmeasurable, score resting on freshness alone. **A thin-tier benchmark
cannot be compared with the partial-tier comparators at all**, which is
precisely how Candidate 1 died. The test would reproduce that failure
having cost a fetcher, a matcher and a curation pass first.

---

## Work estimate, for the record

| piece | estimate |
|---|---|
| fetcher for 76 × ~400 JSON files, aggregated to per-model scores | half a day |
| model-name matching and external date assignment | 1–2 days, and it is where this project's bugs live |
| keeping the verified and public populations separate | blocked — no data file found for the verified set |
| catalog entry and curation | half a day |
| **total** | **~3 days, to produce a THIN-tier entry that cannot be compared** |

---

## What would change the verdict

1. **A dated, verified-population export from ARC Prize.** If the
   semi-private leaderboard is ever published as data, the population
   problem and the two-quantities problem both go away.
2. **Any source with ≥30 pre-2025 models on ARC-AGI-1.** The 2024 ARC
   Prize technical report (arXiv 2412.04604) carries dated results and
   is the obvious place to look; it was not examined here because the
   verdict does not turn on it — a report table is unlikely to reach 30
   models.
3. **Accepting a different question.** ARC-AGI-1 scored *today*, on
   today's population, is perfectly measurable — but "is ARC-AGI-1
   saturated in 2026?" is not the old-but-unsaturated test and should
   not be presented as one.

**Recommendation: do not build it.** Add ARC-AGI-1 to the catalog as an
ordinary present-day entry if it is wanted for coverage — that is cheap
and honest — but not as a validation test. **The forward test remains the
only live route to validating the scoring**, which is the situation the
retirement of the backtest already put the project in.
