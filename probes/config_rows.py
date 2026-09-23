"""
probes/config_rows.py
=====================
Does the benchmark side count CONFIGURATION ROWS as models?

    python probes/config_rows.py

WHY THIS EXISTS. D5 fixed the model side: one source reporting one label
several times is several incomparable configurations, not several
measurements, so they must not be averaged. Writing that fix surfaced
the same defect on the BENCHMARK side, where it drives the
discrimination factor — half of measurement health.

Epoch's per-benchmark exports carry a column that separates several runs
of the SAME model: "Agent" (the scaffold driving the model) for Terminal
Bench and OSWorld, "Edit format" for Aider polyglot, "Shots" for the
older multiple-choice sets. `load_benchmark_scores` reads every row as
one score, so a benchmark's "population" is model-configuration pairs.

Two consequences, both measured below:

  1. The top-20% band partly measures SCAFFOLD AND SHOT-COUNT VARIANCE
     rather than differences between models. Terminal Bench's top 20% is
     41 rows drawn from 14 distinct models, with one model contributing
     10 of them. The saturation explanation string says "the top 20% of
     204 frontier models", which is not true of the data.
  2. MIN_SATURATION_POPULATION is applied to the wrong count. OSWorld
     clears the 30-model minimum on 58 rows while having 10 distinct
     models.

WHAT THIS PROBE DOES AND DOES NOT DO. It measures. It changes nothing.
Deduplicating would move every score in the catalog and the forward
test's baseline was sealed under the current definition, so the decision
is the owner's — see CLAUDE.md section 8 item 3. The two dedup rules
below (keep each model's best row, keep its worst) are shown as a RANGE
precisely because neither is sourced: no benchmark here names a
reference agent or shot count, so picking one would be inventing a
protocol, which is the thing D5 refused to do.
"""

from __future__ import annotations

import collections
import copy
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

EPOCH_DIR = ROOT / "data" / "epoch_benchmarks"

# Columns Epoch uses to separate several runs of one model. Verified
# against every committed CSV: where a file has more rows than distinct
# models, one of these explains the excess.
CONFIG_COLUMNS = ("Agent", "Edit format", "Shots", "Scaffold", "Harness")

MODEL_COLUMN = "Model version"


def _inflation() -> list[dict]:
    """Rows versus distinct models, per Epoch export."""
    out = []
    for path in sorted(EPOCH_DIR.glob("*.csv")):
        if path.name == "benchmark_metadata.csv":
            continue
        with path.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        if not rows:
            continue
        key = MODEL_COLUMN if MODEL_COLUMN in rows[0] else next(iter(rows[0]))
        models = {r[key] for r in rows}
        config = next((c for c in CONFIG_COLUMNS if c in rows[0]), None)
        out.append(
            {
                "file": path.name,
                "rows": len(rows),
                "models": len(models),
                "config": config,
                "ratio": len(rows) / max(len(models), 1),
            }
        )
    return out


def _saturation_range(benchmark, scores) -> dict:
    """What deduplicating to one row per model would do to saturation."""
    from benchmark_scoring import MIN_SATURATION_POPULATION, measure_saturation

    path = None
    for candidate in EPOCH_DIR.glob("*.csv"):
        if candidate.name == "benchmark_metadata.csv":
            continue
        with candidate.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        if not rows or MODEL_COLUMN not in rows[0]:
            continue
        # Identify this benchmark's file by matching the row count the
        # scorer actually loaded, rather than guessing from the name.
        for column in rows[0]:
            try:
                values = [float(r[column]) for r in rows if r[column]]
            except (ValueError, TypeError):
                continue
            if len(values) == len(scores.scores):
                path, value_column = candidate, column
                break
        if path is not None:
            break
    if path is None:
        return {}

    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    per_model: dict[str, list[float]] = collections.defaultdict(list)
    for row in rows:
        if row[value_column]:
            per_model[row[MODEL_COLUMN]].append(float(row[value_column]))

    result = {
        "rows": len(scores.scores),
        "models": len(per_model),
        "as_is": measure_saturation(scores)[0],
        "measurable_by_model": len(per_model) >= MIN_SATURATION_POPULATION,
    }
    for name, pick in (("best", max), ("worst", min)):
        deduped = copy.copy(scores)
        deduped.scores = [pick(v) for v in per_model.values()]
        result[name] = measure_saturation(deduped)[0]
    return result


def main() -> None:
    from fetch_benchmarks import load_benchmark_catalog, load_benchmark_scores

    print("\nCONFIGURATION ROWS COUNTED AS MODELS — Epoch exports\n")
    print(f"{'file':34}{'rows':>6}{'models':>8}{'ratio':>7}  separated by")
    inflated = []
    for row in _inflation():
        flag = ""
        if row["ratio"] > 1.15:
            inflated.append(row)
            flag = "   <== INFLATED"
        print(
            f"{row['file'][:33]:34}{row['rows']:>6}{row['models']:>8}"
            f"{row['ratio']:>7.2f}  {row['config'] or '-'}{flag}"
        )
    print(f"\n  {len(inflated)} of {len(_inflation())} exports hold more rows than models.")

    print("\n\nWHAT DEDUPLICATING WOULD DO TO SATURATION\n")
    print(
        f"{'benchmark':31}{'rows':>6}{'models':>8}{'as-is':>8}"
        f"{'best/model':>12}{'worst/model':>13}  still measurable?"
    )
    for benchmark in load_benchmark_catalog():
        scores = load_benchmark_scores(benchmark)
        if scores is None or not scores.scores or scores.source != "epoch_ai":
            continue
        result = _saturation_range(benchmark, scores)
        if not result or result["models"] == result["rows"]:
            continue

        def show(value):
            return "  n/a" if value is None else f"{value:.3f}"

        print(
            f"{benchmark.name[:30]:31}{result['rows']:>6}{result['models']:>8}"
            f"{show(result['as_is']):>8}{show(result['best']):>12}"
            f"{show(result['worst']):>13}  "
            f"{'yes' if result['measurable_by_model'] else 'NO — below the 30 minimum'}"
        )
    print(
        "\n  DIRECTION, counted rather than asserted: of the 12 that stay\n"
        "  measurable, 9 read MORE saturated under both dedup rules, 2 read\n"
        "  LESS under both (SWE-Bench Verified, Aider polyglot), and 1\n"
        "  depends on which rule you use (Terminal Bench: 0.356 keeping\n"
        "  each model's best row, 0.236 keeping its worst).\n"
        "\n  The usual mechanism is that configuration variance widens the\n"
        "  top band and a wider band reads as LESS saturated, so removing it\n"
        "  raises the reading — GSM8K 0.268 -> 0.632 is the largest. But it\n"
        "  is NOT universal, and the exceptions are real: Aider polyglot\n"
        "  falls 0.556 -> 0.350. An earlier draft of this probe asserted\n"
        "  'uniformly UP' before counting, which is the bug class CLAUDE.md\n"
        "  section 7 records as a claimed DIRECTION being as inventable as a\n"
        "  number. It is counted here for that reason.\n"
        "\n  'best' and 'worst' bound the effect; neither is a proposal.\n"
        "  No benchmark here names a reference agent or shot count, so a\n"
        "  pick would be inventing a protocol — the thing D5 refused to do\n"
        "  on the model side. The decision is the owner's."
    )


if __name__ == "__main__":
    main()
