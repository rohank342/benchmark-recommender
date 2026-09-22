PROJECT BRIEF — benchmark-recommender

Read this before doing anything. It's the accumulated context for a project
you have no memory of. At the end there are standing instructions about how
I want you to work; those matter as much as the technical content.

Last updated 2026-09-21.

═══════════════════════════════════════════════════════════════════════
1. WHAT THIS IS
═══════════════════════════════════════════════════════════════════════

A tool that scores LLM *benchmarks* for whether they still work, and ranks
models downstream of that.

The thesis: a benchmark's popularity is not evidence that it still
discriminates between models. Labs optimize against well-known benchmarks
until the leaderboard stops separating them, and public test sets leak into
training corpora. So "which model is best?" is downstream of a question
nobody asks: which measurement is still worth believing?

The concrete case, computed from real data: for code generation HumanEval
scores 30.6/100 while MirrorCode scores 76.3. HumanEval is the famous one —
164 short functions from 2021, top ten models spanning 7.9 points and
averaging 92% of the usable range, 8-18% of items in pretraining corpora,
and scoring 39.4% lower on EvoEval.

Repo: github.com/rohank342/benchmark-recommender
Local: ~/benchmark-recommender, branch main, 221 tests, CI green.

WHERE THE PROJECT ACTUALLY STANDS — read this before believing the above.
The backtest (section 4a) gets 10 of 12, loses separation by 17.3 points,
and does NOT beat sorting by release date, which also gets 10 of 12.
Across those twelve, age and measured saturation are uncorrelated
(r = +0.01) while age alone predicts the ground truth at r = +0.79.

A second pre-registered test (Candidate 1, docs/SECOND_TEST_PREREGISTRATION.md)
was run on 2026-09-21 and FAILED: the scorer ranked SWE-Bench Verified
16.6 points ABOVE GPQA Diamond three weeks before OpenAI publicly
abandoned it — the same ordering age gives. Discrimination pointed the
right way (+2.02); specificity overrode it (-16.00).

THE SCORING MACHINERY HAS NEVER BEEN SHOWN TO BEAT AGE ON ANY
DISCRIMINATING COMPARISON. That is the central open problem. Do not
paper over it, and do not tune anything to change it (see the standing
rule in section 8).

═══════════════════════════════════════════════════════════════════════
2. ARCHITECTURE
═══════════════════════════════════════════════════════════════════════

Benchmark side (the point of the project):
  fetch_benchmarks.py        The catalog: 26 benchmarks, 10 categories, all
                             curated fields, evidence dates per claim.
  benchmark_scoring.py       Four factors, penalties, as-of (time-travel)
                             scoring.
  cross_source.py            Do two evaluators agree about the same models?
                             Splits offset (harness difference) from scatter
                             (irreproducibility).
  fetch_benchmark_scores.py  Pulls score distributions from HF leaderboards
                             v1/v2 and EvalPlus; writes a provenance manifest.
                             Also holds RANDOM_BASELINES.
  task_matcher.py            Free-text task description -> benchmark category.
  backtest.py                Scores benchmarks as of a past date, checks
                             against HF's June 2024 retirement decision.
  probes/                    One-off scripts that derive a committed number
                             from a live source. musr_baseline.py is the
                             model: it prints its working and says what it
                             committed. Add one whenever a value is measured
                             rather than read about.

Model side (downstream, weaker):
  fetch_models.py            Hub fetching: three passes (tag search,
                             benchmarked-model resolution, GGUF/MLX variants).
  scoring.py                 Model scoring weighted by benchmark trust.
  enrich_scores.py           Artificial Analysis + Epoch score indexes.
  model_matching.py          Normalizes model names across sources.
  hardware_filter.py         VRAM = weights + KV cache + workspace.
  device_profiles.py         What each device can actually run.

  app.py                     Gradio, two tabs.
  docs/METHODOLOGY.md        Every formula and threshold, plus a list of
                             where the methodology is weakest.
  docs/BACKTEST.md           The one real validation, and its limits.
  docs/BACKTEST_DESIGN.md    What that validation can and cannot establish.
                             The age-vs-saturation correlations live here.
  docs/SPECIFICITY_RUBRIC.md The ADOPTED rubric (v2) for task_specificity.
                             v1 kept below it, superseded.
  docs/SECOND_TEST_PREREGISTRATION.md  Candidate 1, pre-registered and
                             RUN. It failed.
  docs/HINDCAST_PREREGISTRATION.md  Pre-registered and RUN. Descriptive
                             only; the outcome mean-reverted.
  docs/SCORE_SPLIT_PROPOSAL.md  Proposal to separate measurement health
                             from task relevance. NOT implemented.

═══════════════════════════════════════════════════════════════════════
3. THE EVIDENCE STANDARD — NON-NEGOTIABLE
═══════════════════════════════════════════════════════════════════════

This is the spine of the project. Violating it silently is the worst thing
you can do here.

- NEVER invent a number. If evidence is missing, leave a CURATE(you) marker
  saying what to look for. A plausible-looking guess in a table that shows
  one decimal place is a lie with a decimal point.
- Every curated claim carries its basis in `curation_notes`: "RESEARCHED
  <date>" with a citation, or CURATE(you) with what's missing. All 22
  entries currently meet the researched bar.
- `None` means nobody looked. An explicit 0.0 means someone looked and found
  nothing. Tests pin this distinction; don't let it erode.
- Factors report `basis`: measured / curated / unknown. The UI shows it.
- Two tests enforce this: one fails if any entry lacks a researched basis,
  another if any top-5 benchmark does.
- `evidence_dates` records when each claim became public. This is what stops
  the backtest being circular — the saturation flags on the benchmarks HF
  retired are derived FROM that retirement, so they're dated to the
  announcement and invisible at the 2024-06-01 cutoff.

[Section 3 is kept verbatim from the original brief. Two counts in it have
moved since: the catalog is 26 entries, not 22, and all 26 meet the
researched bar. Nothing else in it has changed. Two additions that follow
FROM the standard rather than amending it:

  - A number that is a bound, not an estimate, must say so. The field
    item_error_rate_basis ("estimate" | "lower_bound") exists for this.
    Scoring is identical for both; only the wording changes. Charging a
    bound more harshly would mean inventing a severity the evidence does
    not contain.
  - A value assigned by Claude Code rather than the owner must say that in
    curation_notes. Four task_specificity values currently carry
    "assigned by Claude Code 2026-09-21, not yet reviewed by the owner".
    Specificity is the owner's judgement by design; an unmarked Claude
    value in that field is a violation of this section.]

═══════════════════════════════════════════════════════════════════════
4. SCORING, IN BRIEF
═══════════════════════════════════════════════════════════════════════

Trust = weighted factors, then penalties multiply:
  discrimination 0.40   measured saturation from score distributions
  freshness      0.20   age decay, half-life 730 days, discounted by holdout
  reproducibility 0.20  cross-source scatter where measurable, else a
                        curated evaluator count
  specificity    0.20   computed from five rubric dimensions stored per
                        benchmark (sum/10). Auditable judgement, NOT
                        measurement, and not independently checked.

Penalties: contamination (worse of rate vs observed effect), item error
rate (wrong answer keys), reported saturation (only when unmeasurable).

FIXED 2026-09-21: a contamination flag with no measured rate and no
measured effect now carries NO numeric penalty and is shown as a WARNING.
It used to take a flat 0.65 — identical to what severity = 1 produces — so
"reported, nobody measured it" cost as much as "measured to be maximally
contaminated", and measuring bought nothing. The cost of the fix is that
unmeasured-but-real contamination is now free; SWE-Bench Verified is the
live example. See docs/METHODOLOGY.md.

THE SAME ERROR IS STILL LIVE IN REPRODUCIBILITY — see open work item 4.

Model scoring keeps TWO trusts apart, deliberately: how much to believe the
benchmark, versus how much to believe the report of a model's result on it.
Ranking is tiered before scores compare — confirmed provenance above
unconfirmed, corroborated above self-reported — because a multiplier can't
express "an unverified number is not evidence."

═══════════════════════════════════════════════════════════════════════
4a. THE BACKTEST, AND WHY IT IS THE CENTRAL PROBLEM
═══════════════════════════════════════════════════════════════════════

`python backtest.py --sweep`. In June 2024 HF retired six benchmarks from
the Open LLM Leaderboard and replaced them with six harder ones. All twelve
are catalogued. Scored as of 2024-06-01, do the retired six rank below the
replacements?

Result: 10/12, separation lost by 0.6 points, one inversion (MMLU, retired,
above MuSR, kept). What matters more than the score:

- Sorting by release date and calling the newer half "kept" ALSO gets
  10/12. The four weighted factors add nothing over age on this test.
- Age and measured saturation are uncorrelated across the twelve
  (r = +0.010). Age predicts the retire/keep label at r = +0.793,
  saturation at +0.300.
- Pairwise (36 retired-vs-kept pairs): age 34/36, full trust 35/36,
  saturation alone 22/36. Age's two failures are both rescued by
  saturation and both involve MATH Level 5. So measured saturation's whole
  incremental contribution over age is TWO PAIRS resting on ONE benchmark.
- Four different single-weight changes each produce 12/12, pulling in
  incompatible directions — including HALVING the discrimination weight.
  That is the signature of fitting to twelve points.
- Raising MuSR's unreviewed specificity from 0.30 to 0.34 flips the test
  to 12/12.

Do not tune anything to fix this. The failure is recorded in the test
suite deliberately (tests/test_backtest.py pins the inversion and the lost
separation). The real fix is a second, independent dated decision where
the age baseline and the scorer make DIFFERENT predictions — see
docs/BACKTEST_DESIGN.md for verified candidate events.

═══════════════════════════════════════════════════════════════════════
5. DATA AND KEYS
═══════════════════════════════════════════════════════════════════════

All measured numbers come from committed data in data/. Nothing hits the
network at runtime.

  data/benchmark_scores/     Leaderboard distributions + manifest.json
                             (records column, normalization, baseline).
                             Scoring reads the baseline from the MANIFEST;
                             the fetcher writes it from RANDOM_BASELINES.
                             A test pins the two together — if they drift,
                             saturation is computed against a baseline
                             nothing in the code claims.
  data/epoch_benchmarks/     Epoch AI export, CC-BY, requires attribution.
  data/models_raw.json       Hub models (gitignored).
  data/artificial_analysis.json  (gitignored — free tier is internal-use
                             only, not ours to redistribute).

Keys live in .env (gitignored) as NAME=value: HF_TOKEN,
ARTIFICIAL_ANALYSIS_API_KEY. Source it with `set -a; . ./.env; set +a`.

Epoch has no API — its export is downloaded by hand from
epoch.ai/benchmarks/use-this-data.

Staleness is not cosmetic here: saturation moves, so stale data means stale
conclusions.

═══════════════════════════════════════════════════════════════════════
6. ENVIRONMENT — THINGS THAT HAVE ALREADY BITTEN
═══════════════════════════════════════════════════════════════════════

- Python 3.12, pinned in pyproject.toml. `uv venv` without --python once
  silently picked macOS's EOL 3.9.
- gradio 5.x + huggingface_hub 1.x. gradio 4.44 CANNOT render on 3.12
  (TypeError: unhashable type 'dict' in the jinja2 template cache), and it
  surfaces as a misleading "localhost is not accessible".
- hub 1.x removed list_models(tags=/direction=) — use filter= — and
  configure_http_backend. Code handles both majors.
- CI runs OFFLINE against committed data. A dependency upgrade can break
  every fetcher in the repo and the suite will stay green. If you touch
  deps, smoke-test the fetchers live.
- Hub fetches are long (hundreds of requests). A fetch once wedged for 24
  hours because hub 0.x had no socket timeout.
- Don't rename the working directory mid-session; and if you do rename it,
  the venv needs rebuilding (uv bakes absolute paths into activate).
- openai.com returns 403 to automated fetches. Its pages can be cited but
  not retrieved from here; say so when citing one.

═══════════════════════════════════════════════════════════════════════
7. BUGS ALREADY FOUND — pattern-match against these
═══════════════════════════════════════════════════════════════════════

Every one of these was found by looking at real output, not by planning.
This is the kind of thing worth hunting.

- HF v2 publishes each benchmark twice: "GPQA Raw" (accuracy) and "GPQA"
  (rescaled so chance = 0). Reading the wrong one made GPQA's cross-source
  delta read 24.5 points when the truth was 7.9.
- The archived v1 leaderboard marks `Flagged` True for EVERY row — an
  archive property, not a per-model judgement. Filtering on it silently
  dropped all 7,260 models.
- "SimpleQA" was an alias on SimpleQA Verified — two different benchmarks,
  so OpenAI's scores would have been attributed to Google's.
- Saturation depends on which population you measure. GPQA reads 89%
  saturated among frontier models, 59% among open-community ones. Picking
  the larger sample silently answered a different question.
- A model's name matching a benchmark's label does not mean the repo holds
  those weights (testaccount-ai/Qwen3.8-Max topped the table once).
- MuSR's random baseline was recorded as 0.33 "because it has three
  options". Probing the dataset showed the murder-mystery split is BINARY
  and object placement runs 2-5 options per item; the real aggregate is
  0.371. Assumed chance levels are a whole class of this bug — check the
  items, not the description.
- A claimed DIRECTION of effect is as inventable as a number. "Raising the
  baseline will raise saturation" was written into a commit message as
  fact and was backwards: both saturation terms are fractions of
  (ceiling - baseline), so raising the baseline lowers both. Measure the
  effect before describing it.

═══════════════════════════════════════════════════════════════════════
8. OPEN WORK, ROUGHLY RANKED
═══════════════════════════════════════════════════════════════════════

Re-ranked 2026-09-21. The top three are all the same problem: the project
cannot currently show that its scoring beats a calendar.

═══ STANDING RULE, set by the owner 2026-09-21 ═══
NO FURTHER CHANGES ARE TO BE MADE WITH THE BACKTEST IN VIEW.

The backtest and Candidate 1 have both now been run to a conclusion and
both failed. They have served their purpose: they falsified. Continuing
to adjust inputs while watching those numbers would convert them from
tests into a training set, and every remaining failure is already
understood well enough that another round of tuning would be fitting,
not fixing.

What this permits: changes argued entirely from evidence about the
benchmark itself — a citation, a measurement, a probe, a study. Those may
be committed, and the backtest may be RERUN afterwards and REPORTED, as
was done for GSM8K's contamination effect.

What this forbids: choosing or revisiting any value, weight, threshold or
formula because of what it does to a test result; and re-running a test
to decide whether to keep a change.

The next real move is a test the project has not run: a genuinely
independent dated decision (see docs/BACKTEST_DESIGN.md), or the forward
test at item 7, which cannot be gamed because the outcome has not
happened yet.

1. A SECOND DATED TEST, pre-registered. The existing backtest cannot
   separate the scorer from age, because every retired benchmark in it is
   old and every kept one is new. A second test only helps if it contains
   old-but-still-discriminating or new-but-saturated cases, and if the age
   baseline and the scorer predict DIFFERENT outcomes. Verified candidate
   events with dates and sources are in docs/BACKTEST_DESIGN.md.
2. SPECIFICITY is now rubric-based (v2, adopted 2026-09-21) and computed
   from five stored dimensions per benchmark. That makes it AUDITABLE
   JUDGEMENT, not measurement, and no second reviewer has scored anything
   against the rubric — that check is the highest-value thing the owner
   could personally do. It is also the factor that cost the scorer
   Candidate 1: discrimination pointed the right way by +2.02 and
   specificity pointed the wrong way by -16.00.
   docs/SCORE_SPLIT_PROPOSAL.md proposes separating it out entirely.
3. SATURATION IS NOT A PROPERTY OF A BENCHMARK, it is a property of a
   population snapshot, and this is now measured twice over:
   - BY POPULATION: MATH Level 5 reads 0.938 on Epoch and 0.507 on the v2
     leaderboard; HellaSwag 0.524 vs 0.907; GPQA 0.894 vs 0.588. The
     catalog mixes four populations and the ranking is not like-for-like.
   - BY SAMPLE DATE: over nine months on the SAME source, saturation
     readings mean-reverted almost perfectly (correlation between level
     and change = -0.971) as the v2 population grew 608 -> 4,046 models.
   Both are in docs/METHODOLOGY.md and docs/HINDCAST_PREREGISTRATION.md.
   This undermines the discrimination factor itself and is now the most
   serious technical problem in the project.
4. THE REPRODUCIBILITY FALLBACK REWARDS BEING UNCHECKABLE. ARC scores
   1.000 because its two sources CANNOT be compared (different
   normalizations), while GPQA scores 0.000 because its two sources CAN
   be and disagree. That single mechanism is 20 of the 30 points by which
   ARC outranks GPQA. It is the same error as the old contamination rule,
   which was fixed; this one has not been.
4. REPRODUCIBILITY is measured for 6 of 26 — and the backtest uses NONE of
   those measurements, because as-of scoring has no cross-source data and
   falls back to the curated count. GSM8K gets full marks at the 2024
   cutoff from an unsourced count of 5 while today's measurement says
   0.134. Making curated evidence time-varying would fix this and several
   other as-of distortions.
5. SWE-BENCH VERIFIED'S UPPER BOUND IS UNKNOWN. 0.164 is a floor from
   OpenAI's audit of 27.6% of the set; the other 362 problems have never
   been examined. Separately, a 2026 preprint reports 28.5% of a 49-task
   sample accept an INCORRECT patch — the opposite error. If both hold,
   the benchmark is wrong in both directions and a single item_error_rate
   may be the wrong shape for it.
6. Add HumanEval+ as its own entry. The gap between it and HumanEval is
   direct evidence about how much the original's thin tests let through.
7. A FORWARD TEST. The backtest shows saturated benchmarks score low; the
   claim the tool actually makes is that HIGH scores predict a benchmark
   still discriminating in two years. Untested, and unfalsifiable until
   time passes — which is an argument for starting the clock now.
8. LiveCodeBench has no fetchable score export (leaderboard inlines data in
   a JS bundle). Only benchmark with unmeasured saturation.
9. Model-side VRAM numbers are derived, never measured.

═══════════════════════════════════════════════════════════════════════
9. HOW I WANT YOU TO WORK
═══════════════════════════════════════════════════════════════════════

- Work autonomously through long briefs. Don't stop to ask unless a decision
  genuinely changes direction. Where a call is needed and unspecified, pick
  the option that avoids overstating evidence, note it in a comment, keep
  going.
- Verify against reality, not documentation. Several published API docs have
  been wrong here. Probe the live thing before writing code against it.
- When a test fails, work out whether the test or the code is wrong. Twice
  the test was right and the catalog was internally contradictory.
- NEVER tune parameters to make a result come out right. If a backtest
  fails, show me the failure before proposing changes. A model that only
  works at one weighting is overfit.
- Commit per logical change with a message explaining WHY, including what
  was rejected and what remains uncertain. Don't bundle unrelated work.
- Report findings that undercut the project as prominently as ones that
  support it. If a number I asked for turns out to be meaningless, say so.
- Tell me what you couldn't resolve and why. "I left this as a guess" is a
  useful sentence.
- Don't add features I didn't ask for. Do flag when something you found
  suggests one.
