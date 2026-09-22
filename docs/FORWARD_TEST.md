# Forward test — pre-registration

**Sealed 2026-09-22.** Baseline data:
`data/forward_test/sealed_2026-09-22.json`
SHA-256 of the payload: `4278081a7bebece9483cf1ec53d399d7aa3aeb137a652dcf5874c31eb02c562f`

**This is the only test of this project that cannot be gamed**, because
the outcome has not happened yet. Every other test scored a decision that
was already made and already known. It is also the only route by which
the scoring claim could be vindicated after the evidence-dossier
reframing (`DIRECTION.md`) — that reframing describes what is
established *today*, and this test is what could change it.

## The claim being tested

The backtest asked whether saturated benchmarks score low. **That is not
the claim the tool makes.** The tool tells a reader a benchmark is worth
believing *now*, which is a prediction:

> **Benchmarks with high measurement health today will still be
> discriminating at the horizon; benchmarks with low health will not.**

## What was sealed

For all 26 benchmarks: health, relevance, evidence tier, every factor
with value/weight/basis, measured saturation with its population, the
model count behind it, per-source saturation readings, penalties, and
the rubric dimensions. Plus the complete parameter set — health weights,
`HEALTHY_SPREAD` 0.24, the 20% percentile, the 30-model minimum, both
half-lives, every penalty floor and threshold.

The parameters are sealed because **a prediction made under one
parameter set cannot be scored under another.** If a constant changes
before the horizon, the test is scored with the sealed values, not the
current ones.

Tiers as sealed: **8 full, 15 partial, 3 thin.**

## Horizon

**2028-09-22, two years.** Chosen because HF's v1→v2 retirement cycle ran
about 24 months and OpenAI abandoned SWE-Bench Verified 18 months after
its release, so two years is roughly one observed turnover of the field.
An earlier check at **2027-09-22** may be *reported* but is not the test;
saying so now prevents a one-year look being treated as the result if it
happens to be favourable.

## Outcome measure

**Primary: measured saturation at the horizon**, computed with the
sealed definition (top 20% of a stated population, minimum 30 models)
and the sealed `HEALTHY_SPREAD`.

**Secondary, reported but not scored:** whether the benchmark was
retired, deprecated, or publicly abandoned by a major evaluator in the
interval. This is closer to what "still discriminating" means in
practice but it needs dated events that may not exist for most of the
26, so it cannot carry the test.

### How population comparability is guaranteed at both ends

This is the failure that invalidated the hindcast, so it is fixed in
advance, not afterwards:

1. **Same source at both ends.** Each benchmark's outcome is read from
   the source named in `primary_source` in the sealed file. A reading
   from a different source is not an outcome for that benchmark.
2. **Same population definition at both ends** — the sealed percentile,
   minimum and `HEALTHY_SPREAD`.
3. **Both ends must clear the 30-model minimum.** A benchmark whose
   source cannot supply 30 models at the horizon is **excluded, not
   estimated**, and the exclusion is reported.
4. **Cross-tier comparisons are void**, per the tiering rule. Only
   benchmarks in the same sealed tier are compared with each other.
5. **Growth is recorded, not corrected.** The model count at both ends
   is reported for every benchmark. A benchmark whose population grew
   tenfold and one whose population froze are not silently pooled.

## Pass criterion — fixed now

Among **same-tier pairs where health at seal time and release date order
predict OPPOSITE outcomes** (discordant pairs, the same construction as
the hindcast):

- **PASS:** the scorer is right on **≥ 70%** of discordant pairs, with
  **at least 10 such pairs**.
- **FAIL:** ≤ 40%.
- **INCONCLUSIVE:** anything between, or fewer than 10 discordant pairs.

The 10-pair minimum is the lesson of every previous test here: the
hindcast had 4 and Candidate 1 had 1, and neither could mean anything.
**If the horizon arrives with fewer than 10 discordant pairs, the honest
report is that the test never became runnable** — not a verdict either
way.

## The age baseline — fixed now, in its form

Every test this project has run has been tied or beaten by sorting on
release date, so the baseline is specified before the data exists:

> **Baseline:** rank benchmarks by release date, newest first, within
> the same tier. Its prediction for a pair is that the older benchmark
> will be the more saturated one at the horizon.

Scored on **exactly the same pairs**, by the same rule, and reported
beside the scorer's number every time the scorer's is reported.

**The scorer does not pass by passing. It passes by beating this.** A
result where both reach 70% is a pass for the baseline and an
INCONCLUSIVE for the scorer, and must be reported that way.

## What could invalidate the test before it matures

| event | why it breaks the test | honest response |
|---|---|---|
| **A source archives its leaderboard** (v1 in 2024, v2 in 2025 — this has already happened twice) | the population freezes, so saturation cannot move and the benchmark's outcome is undefined | exclude it and report the exclusion; do **not** substitute another source |
| **A source changes its submission policy** — e.g. Epoch starts accepting community models | the population composition changes underneath a fixed definition, which is the artifact the percentile only partly fixes | report the change, exclude affected benchmarks, and say the test shrank |
| **A benchmark is retired or withdrawn** | no scores at the horizon | this is the *secondary* outcome firing; record it as such and exclude from the primary |
| **The catalog grows** | new benchmarks have no sealed baseline | they are not in the test. Only the sealed 26 count |
| **A parameter is changed** | predictions are not scoreable under different parameters | score with the sealed parameters. If the current code cannot reproduce them, that is a bug to fix before scoring |
| **Fewer than 10 discordant pairs survive** | no power | report "never became runnable" |

## What would count as evidence AGAINST the scorer

1. **≤ 40% of discordant pairs correct.** Anti-predictive on the
   comparisons built to separate it from a calendar.
2. **The age baseline matching or beating it.** Given the backtest's
   30/30 versus 30/30, this is the most likely outcome and it must not
   be presented as a pass.
3. **A result that depends on one benchmark.** If dropping any single
   benchmark flips the verdict, the test measured that benchmark.
4. **Needing to change the design at the horizon.** The criteria above
   are fixed. If they turn out to be unworkable only once the data
   exists, the honest report is that the design failed.

## Provenance

Sealed by Claude Code on 2026-09-22 at the owner's instruction, as the
hedge attached to adopting the evidence-dossier reading in
`DIRECTION.md`. The file is dated and content-hashed; a later run must
add a new dated file rather than overwrite this one.
