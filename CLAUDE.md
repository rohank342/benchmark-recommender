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

THE CONCRETE CASE, stated as evidence about ONE benchmark rather than as
a ranking. HumanEval, re-measured 2026-09-22:

  released 2021-07-07, 164 short functions, public and static ever since
  measured saturation 0.438, over 125 code models submitted to EvalPlus
  13% of items found in a major pretraining corpus (Riddell et al.)
  scores fall 39.4% on EvoEval — but EvoEval does NOT control difficulty,
    so part of that drop is the new problems being harder. Basis recorded
    as "uncontrolled" for exactly this reason.
  item quality never audited: None, which means nobody looked
  measurement health 28.1, resting on 2 of 3 factors — its
    reproducibility is unmeasurable, because only one source covers it

That is the thesis without a ranking: a benchmark everyone quotes, whose
leakage is measured, whose contamination effect cannot be cleanly
separated from difficulty, and whose answer key nobody has checked.

SUPERSEDED HEADLINE, kept so it is not quietly rewritten: this section
used to read "HumanEval scores 30.6/100 while MirrorCode scores 76.3."
That comparison is dead. The two are in different EVIDENCE TIERS —
MirrorCode's score rests on a release date, with 8 scored models and no
measurable saturation — so they are not ranked against each other and
the numbers were never comparable. The thesis never needed the
comparison; see docs/RANK_RANGES.md.

Repo: github.com/rohank342/benchmark-recommender
Local: ~/benchmark-recommender, branch main, 279 tests, CI green.

═══ DIRECTION DECIDED 2026-09-22 — do not relitigate ═══
This project is an EVIDENCE DOSSIER on 28 benchmarks. The per-benchmark
evidence is the product; the composite score is a summary presented as
such, and the ranking is grouped by evidence tier and labelled as a
summary rather than a verdict. See docs/DIRECTION.md for the argument on
both sides.

Adopted because every real finding came from the catalog and every
failure came from the score. It is not a retreat from the scoring claim
— it is an accurate description of what is established TODAY.

THE HEDGE, also decided: the forward test was sealed the same day
(docs/FORWARD_TEST.md, data/forward_test/sealed_2026-09-22.json). It
matures 2028-09-22, its age baseline is fixed in advance, and it is the
only route by which the scoring claim could be vindicated. If it passes
and beats the baseline, revisit the direction then — not before.

WHERE THE PROJECT ACTUALLY STANDS — read this before believing the above.
All figures below re-measured 2026-09-22; the values they replace are
given, because several had drifted far enough to change the emphasis.

The backtest (section 4a) gets 10 of 12, loses separation by 26.9 points
(recorded as 17.3 here and 0.6 in section 4a; both were stale), and does
NOT beat sorting by release date, which also gets 10 of 12.

`probes/findings.py correlations`, across those twelve at the cutoff:

    r(age, kept)          -0.793    age predicts the decision
    r(health, kept)       +0.502    the score predicts it much less well
    r(saturation, kept)   -0.198    (was recorded +0.300 — sign flipped)
    r(age, saturation)    +0.202    (was recorded +0.01)

Saturation is not standing in for age, and it is not predicting the
outcome either. AGE BEATS THE COMPOSITE SCORE ON THE DIRECT COMPARISON,
0.793 against 0.502.

A second pre-registered test (Candidate 1, docs/SECOND_TEST_PREREGISTRATION.md)
was run on 2026-09-21 and FAILED: the scorer ranked SWE-Bench Verified
ABOVE GPQA Diamond three weeks before OpenAI publicly abandoned it — the
same ordering age gives. The margin was recorded as 16.6 points; at the
pre-registration's own as-of date it now re-measures at +1.1
(`probes/findings.py candidate1`). The DIRECTION is the failure and is
unchanged; the magnitude moved with three definition changes. The pair
is also VOID on tiers — thin against partial — which that run could not
have known.

THE SCORING MACHINERY HAS NEVER BEEN SHOWN TO BEAT AGE ON ANY
DISCRIMINATING COMPARISON. That is the central open problem. Do not
paper over it, and do not tune anything to change it (see the standing
rule in section 8).

═══════════════════════════════════════════════════════════════════════
2. ARCHITECTURE
═══════════════════════════════════════════════════════════════════════

Benchmark side (the point of the project):
  fetch_benchmarks.py        The catalog: 28 benchmarks, 10 categories, all
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
  docs/BACKTEST.md           SUPERSEDED as a validation — on its valid
                             comparisons it cannot separate the scorer
                             from a calendar. Kept as history.
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
  docs/FINDINGS.md           THE STANDALONE WRITE-UP, for a reader outside
                             the project: thesis, every test and its
                             result, the bug classes, what is open. Every
                             figure footnoted with the command behind it.
                             Start here when asked what the project found.
  docs/POPULATION_CLIFF.md   MIN_SATURATION_POPULATION is a cliff, not a
                             taper. Quantified; design only, nothing built.

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
moved since: the catalog is 28 entries, not 22, and all 28 meet the
researched bar. Nothing else in it has changed. Two additions that follow
FROM the standard rather than amending it:

  - A number that is a bound, not an estimate, must say so. The field
    item_error_rate_basis ("estimate" | "lower_bound") exists for this.
    Scoring is identical for both; only the wording changes. Charging a
    bound more harshly would mean inventing a severity the evidence does
    not contain.
  - THE UNCHECKABILITY BUG CLASS HAS NOW APPEARED FOUR TIMES. Check any
    new rule against it BY DEFAULT, before adopting it:
      1. reproducibility fell back to an evaluator count whose mean
         (0.580) beat the measurement it replaced (0.485);
      2. an unquantified contamination flag took the maximum penalty,
         so measuring bought nothing;
      3. model-side source disagreement costs nothing, so two sources
         that contradict each other score like two that agree;
      4. evidence depth inverted the ranking TWICE — once on the
         benchmark side (thin scores outranking thick) and once on the
         model side (thin-tier benchmarks weighting more);
      5. UNKNOWN_BENCHMARK_TRUST, chosen as "middling" in the pivot
         commit and never re-derived through two scale changes. NOTE:
         when finally measured it sits above only 8 of 28 health scores,
         not 18 of 26 as an earlier report claimed — the instance is
         real, the severity was overstated. Measure before ranking.
    The test to run on any new rule: does having less evidence, or
    failing a check, ever come out better than having more or passing?
    If the answer needs thought, it is probably yes.
  - A FIELD HOLDING TWO INCOMPARABLE QUANTITIES IS A VIOLATION OF THIS
    SECTION, even when both values are sourced. contamination_effect held
    HumanEval's 0.394 (EvoEval, difficulty NOT controlled) beside GSM8K's
    0.051 (GSM1k, difficulty-matched); both were real published numbers
    and the penalty formula could not tell that they measured different
    things. "Sourced" is necessary and not sufficient — the question is
    whether two values in one field can be compared. The remedy is a
    basis field: item_error_rate_basis, contamination_effect_basis. Scoring
    stays identical across bases, because discounting one would mean
    inventing a correction; only the wording changes.
  - A COMPARISON ACROSS EVIDENCE TIERS IS NOT A CLAIM THIS PROJECT
    MAKES. Two health scores are comparable only when they rest on the
    same evidence: a score built from three measured factors and one
    built from a release date are not two points on one scale, however
    similar the arithmetic looks. This is not a display convention, it
    is a limit on what may be ASSERTED — in a doc, a commit message, a
    report or the UI. The founding headline died of exactly this
    (section 1), the backtest's six void pairs are exactly this
    (section 4a), and Candidate 1 turned out to be this too. When a
    comparison spans tiers the honest output is "these are not
    comparable", not a hedged number. Same-tier comparisons are still
    subject to everything else here.
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

HEALTH IS NOT A CONSTANT — IT DECAYS EVERY DAY. Freshness is an age
decay, so every health score falls as the clock advances, with no change
to the repo. MEASURED 2026-09-23: mean catalog health falls 0.0286
points per day (`python probes/findings.py decay`; two adjacent as-of
dates isolate it, since no evidence became public between them). So ANY
HEALTH FIGURE IN A DOCUMENT IS EXACT ONLY ON THE DATE BESIDE IT, and
tests/test_doc_figures.py has to allow for it explicitly — three entries
carry a `decays` flag with a wider tolerance, and a test forbids a
decaying figure from sitting on the default one, which would go red
within days and train everyone to ignore the file. This was noticed only
because a session crossed midnight and a figure quoted that morning no
longer reproduced that evening.

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

ALL FIGURES IN THIS SECTION RE-MEASURED 2026-09-22. The ones they
replace are shown, because four of them had drifted and two had drifted
far enough to reverse their meaning.

Result: 10/12, separation lost by 26.9 points (was recorded 0.6), one
inversion — MATH LEVEL 5, kept, below five retired benchmarks (was
recorded as MMLU above MuSR; that is no longer the inversion). What
matters more than the score:

- Sorting by release date and calling the newer half "kept" ALSO gets
  10/12. The weighted factors add nothing over age on this test.
- FRESHNESS ALONE gets 10/12 and loses separation by only 6.3 points,
  against the full scorer's 26.9. Discrimination alone gets 6/12, which
  is chance; reproducibility alone 6/12 at -60.0. On this test the
  age-derived factor OUTPERFORMS all of them combined on the margin.
- Pairwise, ONLY 30 OF THE 36 retired-vs-kept pairs are valid: six span
  evidence tiers and are void, and all six involve MATH Level 5 (29
  models at the cutoff, therefore thin). On the 30 valid pairs the
  scorer gets 30/30 and the calendar gets 30/30 — the test cannot
  separate them, and that is why it is retired (section 8, item 1).
- Over all 36 pairs INCLUDING the void ones, purely as a correction to
  what this section used to claim: age 34/36, health 31/36, saturation
  20/30. It said "age 34/36, full trust 35/36" — i.e. it recorded the
  scorer BEATING age by one pair. Re-measured, the scorer LOSES to age
  by three. That was the single figure most favourable to the project
  anywhere in this brief, and it does not survive.
- "Four different single-weight changes each produce 12/12" is FALSE.
  No weight setting in the sweep reaches 12/12; the maximum is 10/12.
- "Raising MuSR's specificity from 0.30 to 0.34 flips the test to 12/12"
  is DEAD: specificity is not in the health score since the split, and
  a test pins that no rubric change to any of the twelve can move this
  result at all.

Do not tune anything to fix this. The failure is recorded in the test
suite deliberately (tests/test_backtest.py pins the inversion and the lost
separation), and those tests were RIGHT while this section had drifted.
The real fix is a second, independent dated decision where the age
baseline and the scorer make DIFFERENT predictions — see
docs/BACKTEST_DESIGN.md for verified candidate events.

NOTE ON THE COMMAND. `backtest.py --sweep` raised ZeroDivisionError from
commit e247226 until 2026-09-22 — 28 commits — so the single-factor
comparison and the release-date baseline, which print after the crash
point, did not run at all in that window. That is how these figures
drifted without anyone noticing. Section 7 records the class.

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
- A DIAGNOSTIC NO TEST RUNS IS A DIAGNOSTIC THAT MAY BE SILENTLY DEAD.
  EVERY COMMAND A DOCUMENT CITES AS EVIDENCE IS SMOKE-TESTED IN CI.
  tests/test_diagnostics.py runs each one in a subprocess and fails on a
  non-zero exit or a missing output section. It also fails if a document
  starts citing a command that is not covered, and if a probe is added
  without one — so the guarantee cannot quietly lapse. This exists
  because `backtest.py --sweep` crashed for 28 commits while the suite
  stayed green (section 7). Commands that genuinely cannot run offline
  are listed in UNCOVERABLE with the reason; adding to that list is
  widening a hole and needs to say why.
  SMOKE TESTS ASSERT LIVENESS, NOT VALUES. Numbers are checked
  separately, in tests/test_doc_figures.py. A crashed diagnostic and a
  moved number are different failures and must fail differently.
- Hub fetches are long (hundreds of requests). A fetch once wedged for 24
  hours because hub 0.x had no socket timeout. CHECKED 2026-09-23: the
  repo now runs huggingface_hub 1.32.0, where `configure_http_backend`
  no longer exists and the 30s shim in fetch_models.py is therefore
  inert — 1.x applies its own DEFAULT_REQUEST_TIMEOUT of 10s instead. So
  the wedge risk is covered, but by the library rather than by our code.
  If the repo ever drops back to hub 0.x, the shim becomes live again.
- THE HUB RATE-LIMITS AT 1000 API REQUESTS PER 5 MINUTES, and the GGUF /
  MLX variant pass trips it: it issues one search per benchmarked model.
  The client backs off and retries ("Retry after 150 seconds (0/1000
  requests remaining in current 300s window)") rather than failing, so
  the fetch still completes — it just takes far longer than the request
  count suggests. Budget for the backoff, do not assume the run has
  wedged, and do not add parallelism to "speed it up": that makes it
  worse. THE TOKEN DOES NOT HELP, observed rather than assumed: this run
  was authenticated (HF_TOKEN sourced from .env, confirmed present in
  the process environment) and hit the 1000/5min quota anyway. An
  earlier draft of this note asserted that a token raises the quota,
  which is the section 7 inventable-claim class — the message names a
  PRO/Team/Enterprise upgrade, not authentication.
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
- TOP-K OF N IS NOT ONE STATISTIC. Saturation read the top 10 models,
  which is the top 30% of a 33-model population and the top 0.2% of a
  4,575-model one. Readings moved by up to 0.81 with no change to the
  benchmark. Fixed 2026-09-22 with a percentile; any "top k" over
  variable-sized groups is this bug.
- BEING UNCHECKABLE USED TO PAY. Two separate mechanisms rewarded having
  no evidence: an unquantified contamination flag took the maximum
  penalty multiplier, and an unmeasurable reproducibility fell back to an
  evaluator count whose mean (0.580) was HIGHER than the measurement it
  replaced (0.485). ARC scored 1.000 because its sources could not be
  compared. Whenever a fallback exists, check whether it pays better than
  the thing it stands in for.
- A TEST CAN BE "PASSED" BY HAVING NOTHING TO SAY. Candidate 1 flipped
  from FAIL to PASS when SWE-Bench Verified's discrimination became
  unmeasurable (18 models, below the minimum) and dropped out of its
  score. The pre-registration had already named this as evidence
  AGAINST. A result that improves because a factor vanished is not a
  result.
- COMPARING TWO BENCHMARKS CAN MEAN COMPARING TWO POPULATIONS. Candidate
  1 put SWE-Bench Verified (18 dated models) against GPQA Diamond (196)
  and read the top 56% against the top 5%. This was caught only by
  auditing a result that had already been reported.
- MORE EVIDENCE CAN SCORE LOWER THAN LESS. Dropping unmeasurable factors
  and renormalizing the rest made a score resting on one factor
  arithmetically comparable to one resting on three — and the thinnest
  score in the catalog ranked first (MirrorCode 95.1 on a release date).
  Fixed 2026-09-22 with evidence tiers. Any normalization that makes
  unequal evidence look equal is this bug.
- A CONSTANT CAN OUTLIVE THE DEFINITION IT WAS CALIBRATED FOR.
  HEALTHY_SPREAD = 0.20 was set against top-10 spreads and survived the
  move to a top-20% band, so every absolute saturation level in the
  catalog was on a scale nothing was calibrated for. When a definition
  changes, every constant that touches it is stale until re-derived.
- THE MODEL SIDE DID NOT INHERIT THE BENCHMARK SIDE'S FIXES. scoring.py
  weights by raw health, so evidence tiering never reached it. Real in
  the mechanism, and ZERO impact on current data — no model result cites
  a thin-tier benchmark. Ranking a finding by mechanism before measuring
  its impact is itself the bug; measure first.
- SOURCE DISAGREEMENT COSTS NOTHING ON THE MODEL SIDE, and there is
  exactly ONE instance of measurable disagreement in the whole dataset
  (0.022 points). Sources cover disjoint benchmarks, so there is usually
  nothing to disagree about.
- raw_benchmark_score AVERAGES INCOMPARABLE QUANTITIES — a HumanEval
  pass@1 with an Artificial Analysis coding index. Needs a design
  change, not a basis field: a basis records one claim whose kind
  varies, and this is a mean over several kinds.
- 70% OF MODEL-SIDE EVIDENCE IS UNRECOGNISED BENCHMARKS at a flat 45.0,
  which is higher than 18 of the 26 catalogued health scores, and 59% of
  scored models rest on nothing else. This dominates model scoring far
  more than any weighting rule does.
- A DEFAULT CAN DRIFT WITHOUT BEING TOUCHED. UNKNOWN_BENCHMARK_TRUST
  has been 45.0 since the pivot while the scale under it moved twice
  (unmeasurable factors dropped, HEALTHY_SPREAD derived). Up to 33 of 81
  models' ranks depend on it. When a scale changes, every constant
  EXPRESSED IN THAT SCALE is stale, not just the ones that were part of
  the change.
- A COMPOSITE INDEX IS NOT A BENCHMARK, and counting one as such
  double-counts. artificial_analysis_coding_index is 28% of all model-
  side citations and aggregates benchmarks this catalog already weighs
  separately, so those components are counted twice — once assessed,
  once inside an unassessed aggregate.
- "DISJOINT COVERAGE" WAS THREE ARTIFACTS, NOT A GAP. Of 131
  unrecognised citations: 52 are one composite index, 20 are one model's
  card listing 20 variants of a single label, and ~50 distinct labels
  come from ONE model (bloomz-560m) enumerating its multilingual suite.
  57 of 60 unrecognised labels are cited exactly once. Citation-weighted
  coverage is the wrong metric; model-weighted coverage (42% of models
  have at least one catalogued citation) is the meaningful one.
- THE SAME SOURCE REPORTS THE SAME BENCHMARK MANY TIMES, and all of them
  were averaged. 19 (model, label, source) groups hold 2+ entries,
  covering 66 of 323 citations; spread median 0.040, max 0.620.
  bigcode/gpt_bigcode-santacoder carries TWENTY entries under "MultiPL
  HumanEval (Python)" ranging 0.15 to 0.77. Checking for cross-SOURCE
  disagreement misses this entirely — there is none in the dataset —
  while a five-fold spread under one label was silently meaned. FIXED
  by D5 on the model side; SEE SECTION 8 ITEM 3, the benchmark side has
  the identical defect and it is still live there.
- A DIAGNOSTIC CAN STOP RUNNING WITHOUT ANYTHING GOING RED.
  `backtest.py --sweep` — the command section 4a names as the project's
  headline test — raised ZeroDivisionError for 28 commits, from e247226
  (drop-and-renormalize) to 2026-09-22. Isolating one factor sets the
  others to weight 0; when the survivor was a factor the benchmark had
  dropped as unmeasurable, the renormalizer divided by a zero total. The
  guard tested the LIST of kept factors, not their total weight. No score
  was ever wrong, because production weights are all non-zero — but the
  single-factor comparison and the calendar baseline print AFTER the
  crash point, so the one diagnostic that asks whether the scorer beats
  a calendar silently stopped running, and four figures in this brief
  drifted in the dark. The suite stayed green throughout: it never
  invokes the sweep. WHENEVER A RULE CHANGES WHAT A COMPUTATION
  INCLUDES, CHECK THE CALLERS THAT SET WEIGHTS TO ZERO — and run the
  commands this brief names, rather than trusting the numbers beside
  them.

- THE FOUNDING HEADLINE DIED OF A TIER COMPARISON, and its numbers were
  never stable. "HumanEval scores 30.6/100 while MirrorCode scores 76.3"
  is quoted in this repo in at least three different numeric forms; today
  the same two read 28.1 and 95.1. It was not retired for being
  unflattering — the gap WIDENED — but for never having been a
  comparison: partial tier against thin tier, 125 scored models against
  8. A claim whose numbers drift between retellings was never resting on
  those numbers. Section 3 now forbids the class outright.

- A HARD THRESHOLD IS A CLIFF IN MECHANISM AND A PLATEAU IN PRACTICE —
  AND THE DIFFERENCE IS WHETHER ANYTHING IS STANDING NEAR IT.
  MIN_SATURATION_POPULATION = 30 does not degrade a score as a
  population shrinks; it removes a factor and moves the benchmark to
  another evidence tier. But measured at FINE steps it is completely
  inert from 17 to 35 inclusive — zero rank moves, zero tier changes —
  so 30 sits inside a 19-wide plateau, and no redesign is warranted.
  Two corrections are recorded in docs/POPULATION_CLIFF.md, both of
  them about looking more closely before designing: an earlier report
  said the unstable benchmarks sit "within a few models" of the
  threshold (they sit 5 to 8 ABOVE it), and the document was originally
  written as if a cliff needed fixing, on a coarse sweep that only
  sampled 20/25/30/35/40. WATCH LIST, the three that would end the
  plateau: SWE-Bench Verified 35, FrontierCode 35, GSO-Bench 38.
  CAVEAT THAT UNDERCUTS IT: those are ROW counts. OSWorld looks clear
  at 57 and has 10 distinct models (section 8 item 3), so counting
  models instead of rows would recompute the whole plateau.

- ROWS ARE NOT MODELS, AND THE DEFECT TRAVELS UPWARD. D5 fixed one
  source reporting one label several times on the MODEL side. The
  identical defect was sitting one layer up, on the benchmark side,
  where it drives 50% of health — and it was found only because fixing
  the lower layer made the pattern recognisable. 13 of 20 Epoch exports
  hold more rows than distinct models, separated by an Agent / Edit
  format / Shots column; both HF leaderboards do it at 1.02-1.05x via
  Precision. Terminal Bench's top 20% is 41 rows from 14 MODELS, one
  contributing 10, while the reading says "the top 20% of 204 frontier
  models". WHEN A DEFECT IS FIXED AT ONE LAYER, CHECK THE LAYER ABOVE
  AND BELOW IT BEFORE CLOSING THE ITEM. Also: cross_source averages a
  model's rows too, so reproducibility carries it as well.

- A ROW WITH NO MODEL IS NOT A MODEL. 188 rows across 10 benchmarks
  carry an empty Model version. OSWorld is 37 of 57 (65%), and they are
  AGENT-ONLY submissions where the agent is the system. No collapsing
  rule repairs that: OSWorld's saturation is measuring agents whatever
  is done on top. Merging blank names into one group — which an earlier
  version of probes/config_rows.py did — silently deleted dozens of rows
  from the top band and produced GSM8K 0.632 where the truth is 0.289.
  CHECK FOR EMPTY KEYS BEFORE GROUPING ON A KEY.

- THE HINDCAST MIXED POPULATIONS INSIDE THE DOCUMENT THAT BANS IT. Two
  of its five recorded rows read saturation at T from Epoch and at the
  outcome from v2, when its own POPULATION section fixed v2 at both ends
  for exactly this reason. Found only by making it runnable
  (probes/hindcast.py). BIG-Bench Hard's change flipped sign and GPQA
  Diamond's halved; the pre-registered result did NOT move, because the
  contaminated columns were descriptive. A pre-registration is not
  self-enforcing — if a test is not a script, its design is a wish.

- THE FETCHER DROPPED THE FIELD THAT WOULD HAVE RESOLVED D5.
  _extract_eval_results kept task/dataset/metric_name/metric_value and
  discarded dataset.config and dataset.split, which is where the Hub's
  model-index puts the distinction between six pass@1 entries under one
  label. So "the metadata exists" was half true and the half that was
  missing was missing because this repo threw it away on ingest. WHEN A
  RULE NEEDS A FIELD, CHECK THE INGEST, NOT JUST THE SOURCE.

- A DIRECTION CLAIM WENT WRONG TWICE IN ONE PROBE, IN OPPOSITE WAYS.
  probes/config_rows.py first asserted "the direction is uniformly UP"
  without counting (the inventable-direction class, below). Corrected to
  a count — which was then itself wrong, because the grouping underneath
  it was broken: it matched CSV files by ROW COUNT over an unordered
  glob and merged blank names. The honest figure is 8 up / 0 down / 8
  rule-dependent. COUNTING INSTEAD OF ASSERTING IS NECESSARY AND NOT
  SUFFICIENT; the count is only as good as the grouping under it.

- A STALE FIGURE CAN OVERTURN A RESULT, NOT JUST BLUR ONE. Section 4a
  recorded "pairwise: age 34/36, full trust 35/36" — the single figure
  anywhere in this brief where the scorer BEAT the calendar. Re-measured
  2026-09-23: 31/36. The scorer loses to age by three pairs. Nothing had
  been tuned; the number had simply aged out of the state that produced
  it, and it had been quoted forward across sessions as a live finding.
  Two more in the same pass: Candidate 1's margin +16.6 -> +1.1, and
  r(saturation, label) +0.300 -> -0.198, a SIGN FLIP. The lesson is not
  "re-measure" — that rule already existed — it is that a stale figure
  is not a rounding error waiting to be corrected. It can be carrying a
  conclusion. THIS IS WHY tests/test_doc_figures.py EXISTS: 47 figures,
  86 assertions, four documents, and it fails CI when a doc figure stops
  matching the probe that produces it.

- A PROBE CAN MISREPORT THE PROPERTY IT EXISTS TO CHECK.
  probes/impact.py printed a column headed "% of total weight" that
  summed benchmark HEALTH rather than weight, and so reported thin-tier
  benchmarks as carrying 1% of model-side weight when the thin-tier
  exclusion guarantees 0%. This is the tool section 9 mandates running
  before any scoring change. Fixed; both unrecognised and thin now read
  0%. A measurement of a fix, taken with the wrong instrument, is not
  evidence the fix works.

- A claimed DIRECTION of effect is as inventable as a number. "Raising the
  baseline will raise saturation" was written into a commit message as
  fact and was backwards: both saturation terms are fractions of
  (ceiling - baseline), so raising the baseline lowers both. Measure the
  effect before describing it.

═══════════════════════════════════════════════════════════════════════
8. OPEN WORK, ROUGHLY RANKED
═══════════════════════════════════════════════════════════════════════

Re-ranked 2026-09-23 (FIFTH revision). The catalog is 28 benchmarks.
Completed items are deleted rather than left to rot, and what they
settled is recorded under item 3 so nothing is re-opened by accident.

═══ READ THIS BEFORE PICKING UP WORK ═══
THE PROJECT IS IN A WAITING STATE, and that is the correct state to be
in. Every test of the score has been run to a conclusion; none beat a
calendar; the one live test does not mature until 2028-09-22. The
scoring machinery should NOT be worked on in the meantime — not because
it is finished, but because there is nothing left to check a change
against, and changing it anyway is how a test becomes a training set.

What remains is EVIDENCE work: measuring things that are unmeasured,
sourcing things that are unsourced, and keeping the record honest. That
is items 2 and 4-7. Items marked AWAITING A DECISION are the owner's,
not a session's.

WHAT WOULD JUSTIFY REOPENING SCORING WORK. Written down so a future
session can tell "the evidence changed" from "I got bored of waiting":
  (a) THE FORWARD TEST MATURES (2028-09-22), or its one-year look
      (2027-09-22) is taken and REPORTED — which is explicitly not the
      test, and must not be treated as one however it comes out.
  (b) A GENUINELY INDEPENDENT DATED DECISION becomes available: a
      public retirement, deprecation or abandonment by a major
      evaluator, with a date, where the scorer and release-date order
      make DIFFERENT predictions and both benchmarks are in the SAME
      evidence tier with comparable populations. All three conditions
      killed Candidate 1 and ARC-AGI-1 separately. docs/BACKTEST_DESIGN.md
      lists the shape; pre-register before looking.
  (c) A NEW SCORE SOURCE lands that makes an unmeasurable factor
      measurable for enough benchmarks to change a tier — an EvalPlus-
      style export for LiveCodeBench, MBPP or DS-1000, or any second
      evaluator covering benchmarks this repo already scores, which
      would lift reproducibility above 8 of 28 (item 5).
  (d) A DIFFICULTY-CONTROLLED CONTAMINATION VARIANT is published for a
      benchmark the catalog holds, in the way GSM1k is for GSM8K. That
      would retire the `uncontrolled` basis on HumanEval's 0.394 and is
      the single most valuable external event for item 6.
  (e) THE POPULATION DEFINITION IS DECIDED (item 3). That one moves
      every score, so it reopens scoring by construction — which is
      exactly why it is a decision and not a task.
NONE OF THESE IS A REASON TO RETUNE A WEIGHT. They are reasons to
re-measure. The standing rule below still applies to all of them.

TOP OF THE LIST UNTIL A RULE IS CHOSEN AND THE SECOND SEAL EXISTS:
1. ROWS ARE NOT MODELS — see item 4 below, which is where the detail is.
   It is listed first because it blocks the forward test's PRIMARY seal,
   which cannot be created until the collapsing rule is decided. Nothing
   else on this list gates a sealed baseline.

VALIDATION — one live test, and it is two years out:
2. THE FORWARD TEST, sealed 2026-09-22, matures 2028-09-22, age baseline
   fixed in advance. It is the ONLY live validation. Its seal covers 26
   benchmarks; MBPP and DS-1000 were added afterwards and are correctly
   OUT of it. AMENDMENT 1, 2026-09-23: the sealed readings measure
   saturation over CONFIGURATION ROWS, so a second seal computed over
   distinct models is designated PRIMARY — designated before the
   corrected numbers existed, and committed before they were computed.
   Both seals are evaluated side by side in 2028 whatever they show, and
   a disagreement is itself the finding. THE ORIGINAL SEAL IS IMMUTABLE:
   two literal digests are pinned in tests/test_backtest.py, so it
   cannot be edited even by a session that also updates its hash.
   Protect the seal: add a dated file, never overwrite.
   The backtest is RETIRED on power (scorer 30/30, calendar 30/30 on the
   valid pairs). Candidate 1 is exhausted. ARC-AGI-1 was scoped and
   rejected — only 4 of its 75 available models predate the window
   (probes/arc_agi_population.py).
   The hindcast is now runnable (probes/hindcast.py) and still 2 of 4;
   two rows of its recorded table mixed populations and are corrected in
   place, WITHOUT changing the result.

COVERAGE — the product under Reading B, and where the real gap is:
3. MODEL-WEIGHTED COVERAGE IS 42%: 34 of 81 scored models have at least
   one catalogued citation. Citation-weighted coverage is the wrong
   metric — most unrecognised citations are one composite index and two
   model cards. Adding benchmarks cannot close it.
4. ROWS ARE NOT MODELS (item 1 points here) — the benchmark-side
   version of the defect D5 fixed on the model side, and here it drives
   50% of health.
   INVESTIGATED IN FULL 2026-09-23: docs/CONFIG_ROWS.md,
   probes/config_rows.py. 13 of 20 Epoch exports hold more rows than
   distinct models (Terminal Bench 204/61, TriviaQA 115/39, GSM8K
   235/158), separated by an Agent / Edit format / Shots column. Both
   HF leaderboards do it too at 1.02-1.05x, and there the cause is
   CONFIRMED as Precision — it differs in 355 of 355 v1 duplicate
   groups and 79 of 79 v2 groups.
   AND UNDERNEATH IT: 188 rows carry NO model name. OSWorld is 37 of 57
   (65%), and those are agent-only submissions where the agent IS the
   system. No collapsing rule fixes that one; OSWorld's saturation is
   measuring agents.
   SOURCE CONVENTIONS, cited in the doc: HF documents the cause and
   DELIBERATELY designates no canonical row. Epoch documents mean-across
   -repeated-runs and best-across-scorers (the latter visible in its own
   score_column, "Best score (across scorers)") but documents NOTHING
   for agents, edit formats or shot counts — which is the case causing
   the inflation. So option (i), follow the source, is only half
   available, and that is the finding.
   IMPACT: 7-8 of 28 ranks move, ZERO tier changes under any rule, mean
   health 49.2 -> 47.8-48.6. Direction counted, not assumed: 8 rise
   under every rule, 0 fall under every rule, 8 depend on the rule.
   AWAITING THE OWNER'S DECISION on the collapsing rule. The forward
   test's Amendment 1 (committed BEFORE any of these numbers existed)
   designates the corrected seal PRIMARY and fixes how both seals are
   reported in 2028. Do not create that seal until the rule is chosen.
   TWO OPTIONS NEED NO DECISION and invent nothing: name the population
   accurately in every explanation string, and stop counting rows with
   no model as models.
5. raw_benchmark_score pools incomparable quantities AND within-source
   duplicates. Needs the per-category design change, scoped already.
   Same root as item 4.

   DONE, recorded so they are not re-opened: composites now carry a kind
   and are excluded from weighting with their components listed (D4);
   UNKNOWN_BENCHMARK_TRUST is REMOVED from scoring, unknown benchmarks
   form their own tier below thin (D3); repeated labels now follow the
   benchmark's own canonical protocol where one is documented and are
   weighted not at all where none is (D5). Measured after all three:
   after the 2026-09-23 re-fetch, 56 of 191 models are ranked, 135 are
   shown as unweighted evidence, and unrecognised citations carry 0% of
   model-side weight. (On the smaller pre-re-fetch data: 24 of 81, 57.)
   ALSO DONE, and load-bearing for everything above: every command a
   doc cites is run by CI (tests/test_diagnostics.py) and every
   load-bearing figure is checked against the probe that produces it
   (tests/test_doc_figures.py, 47 figures / 86 assertions / 4 docs).
   Both guard themselves — a doc citing an uncovered command fails, a
   probe added without a smoke test fails, a footnote with no
   registered figure fails. Do not weaken those three.
6. Measurement coverage: reproducibility measured for 8 of 28,
   saturation for 23, a contamination RATE for 3, an item error rate
   for 4 — while 13 of 28 are flagged for contamination with nothing
   quantified, which since the 2026-09-21 fix costs them nothing.
   LiveCodeBench, MBPP and DS-1000 have no score source at all.
   HumanEval+ would make HumanEval's thin tests directly measurable.
7. Verification: SWE-Bench Verified's upper bound unknown, and it may be
   wrong in BOTH directions (a 49-task preprint reports 28.5% false
   ACCEPTANCE against the audit's false rejection); its two penalties
   also come from one non-random 138-problem sample, so they are
   independent defects but not independent observations, and the scorer
   cannot express that. HumanEval's 0.394 not difficulty-controlled
   (DS-1000's perturbation design is the model of what a controlled
   variant looks like). Nobody but Claude Code has scored anything
   against the specificity rubric.

SCORING — demoted and bounded:
8. Seven of nine parameters reorder the catalog. docs/RANK_RANGES.md has
   each benchmark's rank span; only claims about TIERS and DIRECTIONS
   survive, never positions or decimal places. The instability clusters
   at MIN_SATURATION_POPULATION, which is a CLIFF — see
   docs/POPULATION_CLIFF.md, quantified and deliberately unbuilt.
   HEALTHY_SPREAD is no longer on this list as "mis-calibrated": it was
   re-derived from the measured noise floor to 0.24 (3 x the max of 8
   cross-source scatters). Its defensible range 0.084-0.358 still moves
   mean catalog health 56.2 -> 43.8 and up to 19 of 28 ranks, and the
   multiplier 3 is named in the code as the invented element.
9. Saturation still depends on the submission pipeline; an archived
   leaderboard yields a frozen reading. No fix proposed.
10. Relevance is a property of a (benchmark, task) pair, approximated
   per benchmark. VRAM numbers are derived and their estimated flag is
   computed but not shown.

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
test at item 1, which cannot be gamed because the outcome has not
happened yet.

The crash fix of 2026-09-22 is the boundary case for this rule and is
recorded as permitted: it changed no score (the catalog is byte-identical
across it), it was argued from the code rather than from a result, and
the numbers it unblocked are WORSE for the project. Making a broken test
runnable is not tuning. Choosing what it should say would be.

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
- EVERY NUMBER IN A FINAL REPORT MUST COME FROM A PROBE OR COMMAND RUN
  IN THAT SESSION. Never from an earlier report, an earlier commit
  message, or memory. Two figures carried forward this way were wrong by
  the time they were quoted — "45.0 sits above 18 of 26 health scores"
  was 8 of 28 once the scale moved, and "one disagreeing pair, spread
  0.022" was zero pairs (they were two entries from the SAME source).
  Both shaped the next session's priorities before anyone caught them.
  When referencing a figure from an earlier session, RE-MEASURE IT and
  state both values if they differ. Cite the command behind each number
  in the report.
- MEASURE IMPACT BEFORE RANKING OR FIXING ANYTHING. Count how often a
  rule actually fires on real data first. Two model-side findings were
  ranked HIGH on their mechanism; measured, one fired on ZERO of 187
  benchmark citations and the other on ONE model/benchmark pair in the
  whole dataset. A mechanism that is wrong but never exercised is a
  guard to add cheaply, not an urgent fix — and severity claimed without
  a count is the same error as a number without a source.
  `probes/impact.py` exists for this: citations, tiers, weights, and
  per-parameter catalog movement. Run it before changing a scoring rule
  and quote the count in the commit.
- A FIX THAT IMPROVES ONE FAILURE MODE CAN CREATE A WORSE ONE. Dropping
  unmeasurable factors was right on its own terms; combined with the
  30-model minimum it made thin scores outrank thick ones. Before
  adopting a fix, work through how it interacts with the rules already
  in place — especially any rule that changes what gets INCLUDED in a
  computation, because those compose in ways a single-rule reading
  misses. Report the interaction even when the fix is still right.
