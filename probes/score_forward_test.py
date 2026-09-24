"""
probes/score_forward_test.py
============================
Score the forward test. Written 2026-09-24, to be run on 2028-09-22.

    python probes/score_forward_test.py --dry-run   # today's data, rehearsal
    python probes/score_forward_test.py             # the real run, at the horizon

WHOEVER RUNS THIS IN 2028 SHOULD HAVE NOTHING LEFT TO CHOOSE. That is
the whole point of writing it now: every choice made at the horizon is a
choice made knowing the outcome. The pass criterion, the age baseline,
the population rule and the exclusions are all fixed here and in
docs/FORWARD_TEST.md, and this script only applies them.

If something below turns out to be unworkable in 2028, the honest report
is that the design failed — not a revised design. That is stated in
FORWARD_TEST.md under "What would count as evidence AGAINST the scorer",
point 4, and it still holds.

-----------------------------------------------------------------------
STEP 0 — WHAT TO FETCH, AND FROM WHERE

For each benchmark, the seal records `primary_source` and, under
`saturation_by_source`, the per-source reading at seal time. THE OUTCOME
MUST BE READ FROM THE SAME SOURCE. A reading from a different source is
not an outcome for that benchmark; it is a different measurement.

    python fetch_benchmark_scores.py     # HF leaderboards + EvalPlus
    # Epoch: download the export by hand from
    # epoch.ai/benchmarks/use-this-data and unzip to data/epoch_benchmarks/
    python fetch_models.py               # only if the model tab is wanted

Both leaderboards were already archived before this was written (v1 in
2024, v2 in 2025). If a source is gone in 2028, its benchmarks are
EXCLUDED and the exclusion is reported — see the exclusion rules below.

STEP 1 — THE POPULATION RULE AT THE OUTCOME DATE

Identical to the seal's: `BenchmarkScores.one_row_per_model`, the top
`saturation_top_percentile` of at least `min_saturation_population`
distinct models, using the sealed `healthy_spread`. All four values come
from the seal, not from the code as it stands in 2028. If a constant has
changed since, the sealed value wins; if the code cannot reproduce the
sealed reading, that is a bug to fix BEFORE scoring, not a result.

STEP 2 — EXCLUSIONS, fixed in advance

A benchmark is excluded, and the exclusion reported, when:
  * its `primary_source` no longer publishes it;
  * it cannot supply `min_saturation_population` distinct models at the
    horizon (excluded, never estimated);
  * it was retired or withdrawn (this is the SECONDARY outcome firing —
    record it as such and exclude from the primary);
  * it has no sealed baseline, i.e. it was added to the catalog after
    the seal.

STEP 3 — THE PAIRS

Only same-tier pairs count; cross-tier comparisons are void. A pair is
DISCORDANT when health at seal time and release date predict OPPOSITE
orderings of saturation at the horizon — the older benchmark is the one
the scorer ranks better. Concordant pairs cannot separate the two
predictors and are dropped.

STEP 4 — THE VERDICT

  PASS          >= 70% of discordant pairs correct, with >= 10 pairs
  FAIL          <= 40%
  INCONCLUSIVE  anything between, or fewer than 10 discordant pairs

THE SCORER DOES NOT PASS BY PASSING. It passes by beating the age
baseline, scored on exactly the same pairs by the same rule. A result
where both reach 70% is a pass for the CALENDAR and INCONCLUSIVE for the
scorer, and must be reported that way.

STEP 5 — BOTH SEALS

Run this for each seal in data/forward_test/ and report the results side
by side. `sealed_2026-09-24.json` is PRIMARY (saturation over distinct
models); `sealed_2026-09-22.json` is retained and measured saturation
over configuration rows. If they disagree, THE DISAGREEMENT IS THE
FINDING — FORWARD_TEST.md Amendment 1 fixes in advance how each outcome
is to be read, including the one worst for the project.
"""

from __future__ import annotations

import argparse
import itertools
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

SEAL_DIR = ROOT / "data" / "forward_test"
HORIZON = "2028-09-22"
PASS_AT = 0.70
FAIL_AT = 0.40
MIN_DISCORDANT_PAIRS = 10


def _outcome_saturation(entry: dict, parameters: dict) -> tuple[float | None, str]:
    """
    This benchmark's saturation now, read from its sealed source under
    the sealed population rule.
    """
    from benchmark_scoring import measure_saturation
    from cross_source import load_score_sets
    from fetch_benchmarks import find_benchmark

    benchmark = find_benchmark(entry["key"])
    if benchmark is None:
        return None, "no longer in the catalog"
    wanted = entry.get("primary_source")
    for scores in load_score_sets(benchmark):
        if scores.source != wanted:
            continue
        models = len(scores.one_row_per_model().scores)
        if models < parameters["min_saturation_population"]:
            return None, f"only {models} distinct models at the horizon"
        value, _ = measure_saturation(scores)
        return value, f"{models} models from {wanted}"
    return None, f"sealed source {wanted!r} no longer publishes it"


def score(seal_path: Path, dry_run: bool) -> dict:
    sealed = json.loads(seal_path.read_text())
    parameters = sealed["parameters"]

    eligible, excluded = [], []
    for entry in sealed["benchmarks"]:
        value, note = _outcome_saturation(entry, parameters)
        if value is None:
            excluded.append((entry["name"], note))
            continue
        eligible.append({**entry, "outcome_saturation": value, "outcome_note": note})

    scorer_right = baseline_right = discordant = 0
    pairs = []
    for a, b in itertools.combinations(eligible, 2):
        if a["tier"] != b["tier"]:
            continue  # cross-tier comparisons are void
        older, newer = (
            (a, b) if a["release_date"] < b["release_date"] else (b, a)
        )
        if older["health"] <= newer["health"]:
            continue  # concordant: the predictors agree, nothing to separate
        discordant += 1
        # The scorer says the one it ranked better is LESS saturated at
        # the horizon. Age says the older one is MORE saturated.
        scorer_ok = older["outcome_saturation"] < newer["outcome_saturation"]
        scorer_right += scorer_ok
        baseline_right += not scorer_ok
        pairs.append((older["name"], newer["name"], scorer_ok))

    if discordant < MIN_DISCORDANT_PAIRS:
        verdict = "INCONCLUSIVE — never became runnable"
    else:
        share = scorer_right / discordant
        verdict = (
            "PASS" if share >= PASS_AT else "FAIL" if share <= FAIL_AT
            else "INCONCLUSIVE"
        )

    return {
        "seal": seal_path.name,
        "sealed_at": sealed["sealed_at"],
        "population_unit": sealed.get("definition", {}).get(
            "population_unit", "configuration row (implicit)"
        ),
        "eligible": len(eligible),
        "excluded": excluded,
        "discordant": discordant,
        "scorer_right": scorer_right,
        "baseline_right": baseline_right,
        "verdict": verdict,
        "pairs": pairs,
        "dry_run": dry_run,
    }


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="rehearse against today's data; NOT a result",
    )
    args = parser.parse_args(argv)

    from datetime import date

    today = date.today().isoformat()
    if not args.dry_run and today < HORIZON:
        print(
            f"\nREFUSED: the horizon is {HORIZON} and today is {today}.\n"
            "  An early look is not the test. Re-run with --dry-run to\n"
            "  rehearse the machinery; its numbers are not a result and\n"
            "  must not be reported as one."
        )
        return 1

    print(f"\nFORWARD TEST — {'DRY RUN' if args.dry_run else 'SCORED'} {today}\n")
    if args.dry_run:
        print(
            "  *** DRY RUN. THESE NUMBERS ARE NOT A RESULT, AND A DRY RUN\n"
            "  *** WILL ALMOST ALWAYS LOOK FAVOURABLE. Here is why, and\n"
            "  *** why no verdict is printed below at all:\n"
            "  ***\n"
            "  *** The outcome has not happened. Run today, this compares\n"
            "  *** each benchmark's health AT SEAL TIME against its\n"
            "  *** saturation AT SEAL TIME -- the same snapshot on both\n"
            "  *** sides. Health is largely a function of saturation, so\n"
            "  *** the scorer is being asked to predict its own input and\n"
            "  *** it trivially succeeds. That is circular by\n"
            "  *** construction, not evidence of anything.\n"
            "  ***\n"
            "  *** The only thing worth reading from a dry run is that\n"
            "  *** the machinery ran, the seals parsed, and the exclusions\n"
            "  *** behaved. Nothing else. The verdict is withheld rather\n"
            "  *** than labelled, because a label can be cropped away.\n"
        )

    for seal_path in sorted(SEAL_DIR.glob("sealed_*.json")):
        result = score(seal_path, args.dry_run)
        primary = "PRIMARY" if result["population_unit"] == "distinct model" else "retained"
        print(f"  {result['seal']}  [{primary}]")
        print(f"    population unit   {result['population_unit']}")
        print(f"    eligible          {result['eligible']}")
        print(f"    excluded          {len(result['excluded'])}")
        for name, why in result["excluded"][:6]:
            print(f"        {name}: {why}")
        print(f"    discordant pairs  {result['discordant']}")
        print(f"    scorer right      {result['scorer_right']}")
        print(f"    age baseline right{result['baseline_right']:>4}")
        if result["dry_run"]:
            # The computed verdict is deliberately NOT printed. Before the
            # horizon it is circular by construction, and a line reading
            # "PASS" is the single most misquotable thing this repository
            # could emit. The words PASS and FAIL do not appear anywhere
            # in dry-run output; a test enforces that.
            print("    DRY RUN — NOT A RESULT (circular by construction; see above)")
        else:
            print(f"    VERDICT           {result['verdict']}")
        print()

    print(
        "  Report BOTH seals side by side, whatever they show. A result\n"
        "  where the scorer and the calendar both clear 70% is a pass for\n"
        "  the CALENDAR and inconclusive for the scorer. If the two seals\n"
        "  disagree, that disagreement is the finding — see\n"
        "  docs/FORWARD_TEST.md, Amendment 1."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
