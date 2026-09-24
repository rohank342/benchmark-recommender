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

---

# AMENDMENT 1 — 2026-09-23

**Nothing above this line has been modified.** This is an amendment, not
an edit, for the same reason the seal exists at all.

## What was found

The sealed baseline measures saturation over **configuration rows, not
distinct models.**

Epoch's per-benchmark exports carry a column separating several runs of
the *same* model — `Agent` (the scaffold driving it), `Edit format`,
`Shots` — and every row is read as one score. So a benchmark's sealed
"population" is model-configuration pairs, and the top-20% band partly
measures scaffold and shot-count variance rather than differences
between models.

**The case that shows it plainly: Terminal Bench.** Its sealed reading is
taken over **204 rows drawn from 60 distinct models.** The top 20% of
that population is 41 rows from **14** models, one model contributing 10
of them. The reading's own explanation string says "the top 20% of 204
frontier models", which is not a true statement about the data. `9 of 20`
committed Epoch exports hold more rows than distinct models
(`python probes/config_rows.py`).

This is the population-artifact bug class that has now appeared five
times in this project, arriving one layer above the model-side version
fixed the same week as decision D5.

## Why this may be corrected at all

**Because no outcome exists yet.** The horizon is 2028-09-22 and nothing
has been measured against this baseline. Correcting a definition before
any outcome is visible is not the same act as correcting it afterwards,
and only the first is legitimate.

The protection against that distinction being abused is **fixing the
designation before the correction is implemented**, which is what this
amendment does. At the time of writing, no deduplicated saturation
reading has been computed for any benchmark, and the designation below
is therefore not a choice made in the light of what the corrected
numbers turn out to say.

## The amendment

1. **The original seal is retained, unchanged, and will be evaluated in
   2028.** `data/forward_test/sealed_2026-09-22.json`, payload SHA-256
   `4278081a7bebece9483cf1ec53d399d7aa3aeb137a652dcf5874c31eb02c562f`.
   It is immutable. `tests/test_backtest.py` pins both that digest and
   the SHA-256 of the whole file as literals, so the file cannot be
   edited even by a session that also updates its hash.

2. **A second seal will be created once saturation is computed over
   distinct models**, and **it is designated PRIMARY** — now, in advance
   of its own numbers existing.

   The reason is stated before the fact so it cannot be constructed
   afterwards: the original measures configuration variance as if it
   were model spread. A predictor built on "the top 20% of 204 frontier
   models" when the data holds 60 models and 204 model-agent pairs is
   answering a question nobody asked. That is a defect in the
   measurement, independent of which seal turns out to look better in
   2028.

   **Designating the corrected seal primary does not mean the original
   is discarded**, and does not predict which will do better.

3. **Both seals are evaluated and reported in 2028, side by side,
   whatever they show.** Each against its own age baseline, on its own
   discordant pairs, under its own sealed parameters.

4. **If they disagree, the disagreement is itself the finding**, and is
   reported as one rather than resolved in favour of either. A scorer
   whose verdict depends on whether its population counts models or
   model-configuration pairs has told us something about the scorer.
   Specifically:

   | outcome | what it means |
   |---|---|
   | both pass, both beat their baselines | the strongest result available here, and the population question was not load-bearing |
   | both fail | the clearest negative result available here |
   | **primary passes, original fails** | consistent with the row-counting being the defect it looks like — but a single pair of seals cannot establish that, and it must not be reported as though it could |
   | **original passes, primary fails** | reported exactly as prominently. The honest reading would be that the original's apparent success rested on an artifact, which is worse for the project than both failing |
   | either is INCONCLUSIVE (< 10 discordant pairs) | that seal never became runnable; it is not evidence in either direction |

5. **This amendment is committed before any deduplicated reading is
   computed**, and before the investigation in `docs/CONFIG_ROWS.md`
   runs. The commit order is the evidence that the designation was not
   fitted to the numbers.

6. **The second seal is NOT created by this amendment.** The rule for
   collapsing rows to one value per model is the owner's decision, taken
   on the evidence in `docs/CONFIG_ROWS.md`. Until that rule is chosen,
   there is nothing to seal — and a seal created under a rule that was
   later changed would be worthless.

## What has not changed

The horizon, the pass criterion (≥70% of discordant pairs, minimum 10
pairs), the age baseline and its form, the outcome measure, the
population-comparability rules, and every parameter in the original
seal. The amendment changes **how a population is counted**, and nothing
else. Both seals are scored under their own sealed parameters, per the
original design.

---

# AMENDMENT 2 — 2026-09-24: the primary seal exists

**Nothing above this line has been modified.**

## The two seals, for a reader in 2028

| | retained | **PRIMARY** |
|---|---|---|
| file | `data/forward_test/sealed_2026-09-22.json` | **`data/forward_test/sealed_2026-09-24.json`** |
| benchmarks | 26 | 28 |
| payload SHA-256 | `4278081a7bebece9483cf1ec53d399d7aa3aeb137a652dcf5874c31eb02c562f` | `fa6cda364065fde341eddd35792e450a34c6af5dd564cb06c473d61002e1c46b` |
| file SHA-256 | `4e3eb55d7264fc124831fc59a83c4caa43bcfd3d0d5a430e5ba60b690b8a038e` | `f1f4cd7d7a3402871b7b42cb21ef6215691a6cbdad61e51ff5e3e3ad4e096fe9` |
| created by | an uncommitted one-off | `probes/seal_forward_test.py --write`, commit `7c50a4f` |

All four digests are pinned as literals in `tests/test_backtest.py`, so
neither seal can be edited even by someone who also updates its hash.

## The one paragraph that matters

**The two seals differ in exactly one thing: what a "model" is when
saturation is measured.** The 2026-09-22 seal counted every row a source
published, and several sources publish one row per *configuration* — the
agent driving the model, the edit format, the shot count, the numeric
precision. So Terminal Bench was recorded as 204 models when the data
holds 204 model-agent pairs from 60 models, and the top 20% of that
"population" was 41 rows drawn from 14 models, one of them contributing
10. The 2026-09-24 seal measures over distinct models instead: it
follows each source's own rule where one is documented, takes a model's
**best** entry across configurations where none is (a choice, not a
sourced rule — see `CONFIG_ROWS.md`), and drops the 188 rows that name
no model at all. **Every scoring parameter is identical between the two
seals — a test asserts it** — so any difference in their 2028 verdicts
is the population definition and nothing else.

## How to score it

`python probes/score_forward_test.py`, written 2026-09-24 and committed
with this amendment. It refuses to run before the horizon; use
`--dry-run` to rehearse. **A dry run will look like a pass and means
nothing** — it compares health at seal time against saturation at the
same moment, so the scorer is predicting its own input. The script says
so on every dry run.

Its docstring carries the full procedure: what to fetch and from which
source, the population rule, the exclusion rules, the pass criterion,
and the age baseline in its fixed form. **Whoever runs it in 2028 should
have nothing left to choose**, because every choice made at the horizon
is a choice made knowing the outcome.

## What has not changed

Horizon 2028-09-22. Pass at ≥70% of discordant pairs with at least 10
pairs; fail at ≤40%; inconclusive otherwise. The age baseline, its form,
and the rule that the scorer passes only by **beating** it. Both seals
are evaluated and reported side by side whatever they show, and a
disagreement between them is itself the finding — Amendment 1 fixes in
advance how each outcome is to be read, including the one worst for this
project.
