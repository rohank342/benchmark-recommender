# What is this project?

**Design only. Nothing here is implemented.** This is the owner's
decision; the argument is written down so it can be made on the merits.

## The situation

Every test of the score has now been run to a conclusion:

| test | result |
|---|---|
| HF retirement backtest | 10/12, separation lost by 28.9 points. Ties a release-date baseline that also gets 10/12. |
| Candidate 1 (OpenAI abandons SWE-Bench) | Failed at −16.6; now "passes" at +4.1 only because SWE-Bench's discrimination dropped out of the score. **Exhausted as a test.** |
| Hindcast | 1 of 3 discordant pairs. Descriptive only. |

**No test has established that the score beats a calendar.**

Meanwhile the catalog underneath produced every real finding this
project has made: the SWE-Bench audit floor and its contamination, the
MuSR baseline error, GSM8K's mean-vs-maximum effect, HumanEval's
unsupported citation, the population and top-k-of-n artifacts, the
two mechanisms that paid benchmarks for being uncheckable. **None of
those came from the score. All of them came from the evidence.**

---

## Reading A — "a scorer"

*The score is the product; the catalog exists to serve it.*

### What would have to become true

1. **A test the scorer can pass that a calendar cannot.** Not another
   retirement event — those are old→new by construction, which is why
   the candidate list collapsed. It needs old-but-still-discriminating
   or new-but-saturated cases. ARC-AGI-1 at mid-2024 is the only clean
   one identified and it is not yet buildable.
2. **Enough measurement to score on.** Discrimination is measured for 23
   of 26 and reproducibility for 8; the rest is dropped, so scores
   currently rest on 1–3 factors and the highest ones rest on the
   fewest. A scorer whose top-ranked entry is computed from a release
   date is not a scorer.
3. **Thresholds with a basis.** `HEALTHY_SPREAD`, `SCATTER_TOLERANCE`,
   the penalty curves and the factor weights are all judgement, and the
   one that was checked (`HEALTHY_SPREAD`) turned out to be
   mis-calibrated after the percentile change.
4. **Stability under redefinition.** Saturation readings moved by a mean
   of 0.297 when the definition was corrected. A number that moves that
   far on a definitional choice is not ready to rank anything.

### Tests that could establish it

- **ARC-AGI-1 as an old-but-unsaturated case** — the only candidate that
  fills the empty cell. Needs a fetcher and a verified-vs-self-reported
  population decision.
- **A forward test, started now.** Record today's health scores, sealed,
  and check in two years which benchmarks were abandoned. It is the only
  test that cannot be gamed, because the outcome has not happened. It
  is also the only one that tests the claim the tool actually makes.
- **Inter-rater reliability on the rubric.** Cheap, and it bounds how
  much of relevance is signal.

### Honest odds

Two of those four preconditions are years of data collection. The
forward test is the strongest move available and returns nothing for two
years.

---

## Reading B — "an evidence dossier"

*The per-benchmark evidence is the product; the score is a summary and
should be presented as one.*

### The case

The catalog holds, per benchmark: dated evidence with citations,
contamination rates and effects with their basis, item-error audits with
bounds, measured saturation per population, cross-source agreement split
into offset and scatter, holdout type, and a curation note recording
what is known and what nobody has checked. **That is a genuinely useful
artifact and nothing else like it exists** — the individual facts are
scattered across papers, leaderboards and blog posts, and half of them
are misquoted when they travel. This project caught two misquotes in its
own catalog, one of them a figure attributed to two papers that contain
neither.

The score's failures do not damage any of that. They are failures of the
*summary*, and under Reading B a summary that fails to beat a calendar is
a reason to present it more modestly, not a reason to doubt the evidence.

### What changes

**UI.** The detail panel becomes the product and the table becomes an
index. Lead with what is known and what is not: the evidence dates, the
citations, what nobody has audited. Health and relevance stay, presented
as *summaries of the panel below*, not as a verdict. The existing
`rests on` column becomes the second column rather than the fifth.

**README.** Stop leading with "HumanEval 32.6 vs MirrorCode 95.1" — a
comparison that spans two populations and rests on 2 and 1 factors
respectively. *(Done 2026-09-22; the comparison is now marked superseded
in the README, and evidence tiering makes it formally invalid rather
than merely unwise.)* Lead with the thing that is actually defensible: *here is
what is known about each benchmark, with dates and sources, and here is
what nobody has checked.* The saturation numbers become one line of
evidence among several rather than the headline.

**Claims.** "Which benchmark should you believe?" becomes "what is known
about this benchmark, and how much of it is measured?" The thesis —
popularity is not validity — survives intact and is better supported by
the dossier than by the score.

**Open work re-ranks completely.** Coverage and verification rise:
HumanEval+ as its own entry, LiveCodeBench's missing export, the
SWE-Bench upper bound, a difficulty-controlled HumanEval effect,
independent review of the rubric. The scoring items (mis-calibrated
thresholds, the thin-evidence interaction, relevance-per-pair) drop to
presentational concerns.

### The cost

- **It is a smaller claim.** "A well-sourced database" is less
  interesting than "a tool that tells you which benchmark to believe".
- **The score still has to exist and still has to be defensible**,
  because an index needs an order. The mis-calibrated threshold and the
  less-data-higher-score interaction do not disappear; they just stop
  being load-bearing.
- **It concedes the original thesis is unproven.** The project set out to
  show that measured benchmark quality beats popularity and age. It has
  not shown that.

---

## Recommendation: Reading B, with one hedge

**Adopt the dossier framing.** Three reasons:

1. **The evidence is where every finding came from and the score is
   where every failure came from.** That is a strong signal about which
   half is the product. Four sessions of work have improved the evidence
   monotonically and left the score unable to beat a calendar.
2. **Reading A's preconditions are not reachable soon.** The only
   test that could validate the scorer and cannot be gamed is the
   forward test, and it returns nothing for two years.
3. **The dossier is honest about what it is.** Current presentation
   implies a precision the scoring does not have — a ranked table of
   two-decimal numbers, some resting on one factor, some spanning
   incomparable populations. The thin-evidence and population warnings
   added this session are patches on a frame that implies more than it
   should.

**The hedge: start the forward test anyway, this week.** It is nearly
free — record today's health scores with their evidence counts and
populations, sealed and dated — and it is the only route by which
Reading A could later be vindicated. Adopting the dossier framing now
does not foreclose it; failing to start the clock does.

**What I am least sure about.** Reading B's honesty could be a way of
retreating from a claim because it is hard to prove rather than because
it is wrong. The scorer might be right and merely unvalidatable with 26
benchmarks and one dated decision. If the owner's instinct is that the
scoring is sound, the correct response is not to defend it in the UI but
to fund the ARC-AGI-1 test, which is the one piece of evidence that
would settle it.
