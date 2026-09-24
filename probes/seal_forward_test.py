"""
probes/seal_forward_test.py
===========================
Create a dated forward-test seal, or verify the ones already committed.

    python probes/seal_forward_test.py            # verify every seal
    python probes/seal_forward_test.py --write    # create today's seal

A seal is the baseline the forward test is scored against in 2028. It
records, for every benchmark: health, tier, relevance, every factor with
value / weight / basis, measured saturation with its population and model
count, per-source readings, penalties and rubric dimensions — plus the
complete parameter set, because a prediction made under one parameter set
cannot be scored under another.

WHY A SCRIPT. The 2026-09-22 seal was produced by a one-off that was
never committed, so nothing could re-derive its structure or check a
second seal against it. That is the same defect as the hindcast, which
was pre-registered but not a script and turned out to have mixed
populations. A test that is not a script is a wish.

IMMUTABILITY. `--write` refuses to overwrite an existing file. A later
run adds a new dated file; the older seals are never edited. Both
committed seals have their payload digest AND their whole-file digest
pinned as literals in tests/test_backtest.py, so a seal cannot be
changed even by a session that also updates its hash.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

SEAL_DIR = ROOT / "data" / "forward_test"
HASH_FIELD = "sha256_of_payload_without_this_field"


def _payload_digest(payload: dict) -> str:
    """The digest the seal records. Must match the original's recipe."""
    return hashlib.sha256(
        json.dumps(payload, indent=2, sort_keys=True).encode()
    ).hexdigest()


def build(as_of: str) -> dict:
    """Snapshot the catalog as the forward test will be scored from it."""
    from benchmark_scoring import (
        CONTAMINATION_PENALTY,
        FULL_CONTAMINATION_EFFECT,
        FULL_CONTAMINATION_RATE,
        FULL_ITEM_ERROR_RATE,
        HEALTH_WEIGHTS,
        HEALTHY_SPREAD,
        ITEM_ERROR_PENALTY,
        LEAKAGE_HALF_LIFE_DAYS,
        MIN_SATURATION_POPULATION,
        SATURATION_TOP_PERCENTILE,
        measure_saturation,
        score_all_benchmarks,
    )
    from cross_source import MIN_OVERLAP, SCATTER_TOLERANCE, load_score_sets
    from fetch_benchmarks import SPECIFICITY_MAX, load_benchmark_scores

    benchmarks = []
    for trust in score_all_benchmarks():
        b = trust.benchmark
        scores = load_benchmark_scores(b)
        saturation, _ = (None, "") if scores is None else measure_saturation(scores)
        # Per-source readings, so a 2028 run can check it is reading the
        # SAME source and not silently substituting another.
        by_source = {}
        for other in load_score_sets(b):
            value, _ = measure_saturation(other)
            by_source[other.source] = {
                "saturation": value,
                "rows": len(other.scores),
                "models": len(other.one_row_per_model().scores),
                "population": other.population_note,
            }
        collapsed = None if scores is None else scores.one_row_per_model()
        benchmarks.append(
            {
                "key": b.key,
                "name": b.name,
                "release_date": b.release_date,
                "health": trust.health,
                "tier": trust.evidence_tier,
                "relevance": getattr(trust, "relevance", None),
                "evidence": {
                    "factors_possible": 3,
                    "factors_used": sum(
                        1 for f in trust.factors if f.name in HEALTH_WEIGHTS and f.weight
                    ),
                    "measured": sorted(
                        f.name for f in trust.factors if f.basis == "measured"
                    ),
                    "curated": sorted(
                        f.name
                        for f in trust.factors
                        if f.basis == "curated" and f.name in HEALTH_WEIGHTS
                    ),
                    "dropped": sorted(
                        f.name
                        for f in trust.factors
                        if f.name in HEALTH_WEIGHTS and not f.weight
                    ),
                },
                "factors": sorted(
                    (
                        {
                            "name": f.name,
                            "value": f.value,
                            "weight": f.weight,
                            "basis": f.basis,
                        }
                        for f in trust.factors
                    ),
                    key=lambda f: f["name"],
                ),
                "measured_saturation": saturation,
                "models_measured": 0 if collapsed is None else len(collapsed.scores),
                "rows_before_collapsing": 0 if scores is None else len(scores.scores),
                "population": "" if scores is None else scores.population_note,
                "primary_source": "" if scores is None else scores.source,
                "saturation_by_source": by_source,
                "penalties": list(trust.penalties),
                "specificity_dimensions": list(b.specificity_dimensions or ()),
            }
        )

    payload = {
        "purpose": (
            "Forward test baseline, PRIMARY seal. Saturation measured over "
            "distinct models per decision D6. See docs/FORWARD_TEST.md, "
            "Amendment 1. IMMUTABLE."
        ),
        "sealed_at": as_of,
        "definition": {
            "population_unit": "distinct model",
            "collapsing_rule": (
                "BenchmarkScores.one_row_per_model: follow the source where it "
                "documents a rule (Epoch's mean across repeated identical runs, "
                "best across graders); across different configurations take the "
                "model's best (a CHOICE, not a sourced rule); drop rows naming "
                "no model; name the population accurately."
            ),
            "differs_from_2026_09_22": (
                "The original seal measured saturation over CONFIGURATION ROWS. "
                "Terminal Bench read 204 'models' where the data holds 204 "
                "model-agent pairs from 60 models."
            ),
        },
        "benchmarks": sorted(benchmarks, key=lambda b: b["key"]),
        "parameters": {
            "health_weights": dict(HEALTH_WEIGHTS),
            "healthy_spread": HEALTHY_SPREAD,
            "saturation_top_percentile": SATURATION_TOP_PERCENTILE,
            "min_saturation_population": MIN_SATURATION_POPULATION,
            "leakage_half_life_days": LEAKAGE_HALF_LIFE_DAYS,
            "full_contamination_rate": FULL_CONTAMINATION_RATE,
            "full_contamination_effect": FULL_CONTAMINATION_EFFECT,
            "contamination_penalty_floor": CONTAMINATION_PENALTY,
            "full_item_error_rate": FULL_ITEM_ERROR_RATE,
            "item_error_penalty_floor": ITEM_ERROR_PENALTY,
            "cross_source_scatter_tolerance": SCATTER_TOLERANCE,
            "cross_source_min_overlap": MIN_OVERLAP,
            "specificity_max": SPECIFICITY_MAX,
        },
    }
    payload[HASH_FIELD] = _payload_digest(payload)
    return payload


def verify() -> int:
    """Recompute every committed seal's digest. Returns an exit code."""
    failures = 0
    for path in sorted(SEAL_DIR.glob("sealed_*.json")):
        sealed = json.loads(path.read_text())
        claimed = dict(sealed).pop(HASH_FIELD)
        payload = {k: v for k, v in sealed.items() if k != HASH_FIELD}
        recomputed = _payload_digest(payload)
        ok = recomputed == claimed
        failures += not ok
        print(f"  {path.name}")
        print(f"    sealed_at       {sealed.get('sealed_at')}")
        print(f"    benchmarks      {len(sealed.get('benchmarks', []))}")
        print(f"    population unit {sealed.get('definition', {}).get('population_unit', 'configuration row (implicit)')}")
        print(f"    payload digest  {claimed}")
        print(f"    file digest     {hashlib.sha256(path.read_bytes()).hexdigest()}")
        print(f"    intact          {'YES' if ok else 'NO — recomputed ' + recomputed}")
    return failures


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="create today's seal")
    args = parser.parse_args(argv)

    if args.write:
        today = date.today().isoformat()
        path = SEAL_DIR / f"sealed_{today}.json"
        if path.exists():
            print(f"REFUSED: {path.name} already exists. Seals are immutable.")
            return 1
        payload = build(today)
        path.write_text(json.dumps(payload, indent=2, sort_keys=True))
        print(f"wrote {path.name}: {len(payload['benchmarks'])} benchmarks")
        print(f"  payload digest {payload[HASH_FIELD]}")
        print(f"  file digest    {hashlib.sha256(path.read_bytes()).hexdigest()}")
        return 0

    print("\nCOMMITTED FORWARD-TEST SEALS\n")
    return verify()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
