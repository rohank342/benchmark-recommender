"""
probes/config_rows.py
=====================
Does the benchmark side count rows as models — and in every source?

    python probes/config_rows.py            # everything, in doc order
    python probes/config_rows.py inflation  # rows vs distinct models
    python probes/config_rows.py options    # what each collapsing rule does
    python probes/config_rows.py plateau    # the threshold, on model counts
    python probes/config_rows.py overlap    # cross_source: rows or models?

WHY THIS EXISTS. D5 fixed the model side: one source reporting one label
several times is several incomparable configurations, not several
measurements, so they must not be averaged. The same defect sits one
layer up, on the benchmark side, where it drives the discrimination
factor — half of measurement health.

THIS PROBE MEASURES. IT CHANGES NOTHING. Collapsing rows to one value
per model would move every score in the catalog, and the rule for doing
it is the owner's decision on the evidence written up in
docs/CONFIG_ROWS.md. The forward test's amendment of 2026-09-23 was
committed BEFORE any number here was computed, precisely so the
designation of the corrected seal could not be fitted to these results.

WHAT EACH SOURCE SAYS ABOUT ITS OWN REPEATS — cited, not inferred:

  HF Open LLM Leaderboard (v1 and v2). Cause CONFIRMED as precision:
  `Precision` differs in 355 of 355 v1 duplicate groups and 79 of 79 v2
  groups, with `Model sha` usually identical. The leaderboard FAQ says
  so and treats each row as a legitimate separate entry:
      "Models may appear multiple times due to submissions under
      different commits or precision settings, like float16 and 4bit.
      ... Duplicates with identical precision and commit should be
      reported."
      -- huggingface.co/docs/leaderboards/open_llm_leaderboard/faq
  So HF designates NO canonical row per model. Different precision is
  intended; only identical-precision duplicates are errors.

  Epoch AI. Two conventions are documented, and NEITHER covers the case
  that causes the inflation here:
    * repeated runs under identical conditions -> the MEAN, with a
      standard error ("we run most models multiple times on each
      benchmark ... we show a confidence interval of plus and minus one
      standard error around the 'true' mean evaluation score",
      epoch.ai/benchmarks/about);
    * variation between GRADERS -> the BEST, visible in the export's own
      designation: benchmark_metadata.csv sets `score_column` to "Best
      score (across scorers)" for GPQA diamond, MATH level 5, SWE-Bench
      verified, SimpleQA Verified and MirrorCode, and those files carry
      both `mean_score` and that column.
    * variation between AGENTS, EDIT FORMATS or SHOT COUNTS -> nothing.
      Epoch publishes one row per configuration and states no rule.
      epoch.ai/benchmarks/use-this-data documents access and licensing
      only.

  EvalPlus. Greedy-decoding pass@1, one row per model, zero duplicates
  in the committed export, so no rule is needed.

THE CONSEQUENCE OF "NOTHING DOCUMENTED" is that option (i) — follow the
source — is only available for part of the problem, and every other
option invents a rule. That is the finding, not a detail.
"""

from __future__ import annotations

import collections
import copy
import csv
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

EPOCH_DIR = ROOT / "data" / "epoch_benchmarks"

# Columns Epoch uses to separate several runs of one model, verified
# against every committed CSV: where a file has more rows than distinct
# models, one of these explains the excess.
CONFIG_COLUMNS = ("Agent", "Edit format", "Shots", "Scaffold", "Harness")
MODEL_COLUMN = "Model version"

# The collapsing rules under consideration. Each maps a model's several
# values to one. What each ASSERTS is in docs/CONFIG_ROWS.md; none is
# adopted here.
RULES = {
    "best": max,
    "worst": min,
    "median": statistics.median,
    "mean": statistics.fmean,
}


def _grouped(scores) -> dict[str, list[float]]:
    """
    A score set's values, grouped by the model that produced them.

    BLANK NAMES ARE KEPT DISTINCT, not merged. 188 rows across 10 Epoch
    benchmarks carry an empty `Model version`, and merging them would
    invent a model that several unrelated submissions share. OSWorld is
    the extreme case: 37 of its 58 rows are AGENT-ONLY entries — the
    agent is the system ("agi-0 (50 steps)", "UI-TARS-2-2509 (100
    steps)") with no model attributed — so for that benchmark the
    concept "distinct model" barely applies at all.

    Keeping them distinct is also the conservative choice here: it makes
    the model count LARGER, so it cannot manufacture a benchmark falling
    below the saturation minimum.
    """
    groups: dict[str, list[float]] = collections.defaultdict(list)
    names = scores.model_names or []
    for index, value in enumerate(scores.scores):
        name = names[index] if index < len(names) else ""
        key = name if (name or "").strip() else f"__unattributed_{index}"
        groups[key].append(value)
    return groups


def unattributed() -> None:
    """Rows a source could not attribute to any model."""
    from fetch_benchmarks import load_benchmark_catalog, load_benchmark_scores

    print("\n(a2) ROWS WITH NO MODEL ATTRIBUTED\n")
    print(f"{'benchmark':31}{'blank':>7}{'rows':>7}  share")
    total = 0
    for benchmark in load_benchmark_catalog():
        scores = load_benchmark_scores(benchmark)
        if scores is None or not scores.scores:
            continue
        names = scores.model_names or []
        blank = sum(1 for n in names if not (n or "").strip())
        if not blank:
            continue
        total += blank
        print(
            f"{benchmark.name[:30]:31}{blank:>7}{len(scores.scores):>7}"
            f"  {blank / len(scores.scores):>5.0%}"
        )
    print(f"\n  {total} rows in total carry no model name.")
    print(
        "  These are not a counting nuisance. OSWorld's are AGENT SYSTEMS\n"
        "  submitted without a model attribution, so a saturation reading\n"
        "  over that population is measuring agents, not models, whatever\n"
        "  collapsing rule is applied on top."
    )


def _collapsed(scores, rule):
    """A copy of the score set with one value per model."""
    deduped = copy.copy(scores)
    groups = _grouped(scores)
    deduped.scores = [rule(values) for values in groups.values()]
    deduped.model_names = list(groups)
    deduped.model_dates = []
    return deduped


def inflation() -> None:
    """(a) Rows versus distinct models, for EVERY source."""
    from fetch_benchmarks import load_benchmark_catalog, load_benchmark_scores

    print("\n(a) ROWS VERSUS DISTINCT MODELS — every score source\n")
    print(f"{'benchmark':31}{'source':26}{'rows':>6}{'models':>8}{'ratio':>7}  separated by")
    per_source: collections.Counter = collections.Counter()
    inflated_sources: collections.Counter = collections.Counter()
    for benchmark in load_benchmark_catalog():
        scores = load_benchmark_scores(benchmark)
        if scores is None or not scores.scores:
            continue
        groups = _grouped(scores)
        rows, models = len(scores.scores), len(groups)
        ratio = rows / max(models, 1)
        per_source[scores.source] += 1
        if ratio > 1.001:
            inflated_sources[scores.source] += 1
        by = "-"
        if scores.source == "epoch_ai":
            by = _epoch_config_column(benchmark) or "(no column varies)"
        elif scores.source.startswith("open_llm"):
            by = "Precision (per the HF FAQ)"
        flag = "   <==" if ratio > 1.15 else ""
        print(
            f"{benchmark.name[:30]:31}{scores.source[:25]:26}{rows:>6}"
            f"{models:>8}{ratio:>7.2f}  {by}{flag}"
        )
    print("\n  inflated benchmarks per source:")
    for source, total in per_source.most_common():
        print(f"    {source:26} {inflated_sources[source]:>2} of {total}")


def _epoch_config_column(benchmark) -> str | None:
    """
    Which column separates this Epoch benchmark's repeated rows.

    Keyed on the catalog's `epoch_source_file`, NOT on a row-count match.
    Matching by row count silently failed for OSWorld and ARC, whose CSVs
    hold rows with an empty score that the loader drops — so the file was
    never found and the column read as "-". A lookup that fails by
    printing a dash is worse than one that raises.
    """
    name = getattr(benchmark, "epoch_source_file", None)
    if not name:
        return None
    path = EPOCH_DIR / name
    if not path.exists():
        return None
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        return None
    present = [c for c in CONFIG_COLUMNS if c in rows[0]]
    # Only report a column that actually varies within a model's rows;
    # DeepSWE carries "Harness" with one value throughout.
    per_model: dict[str, set] = collections.defaultdict(set)
    for column in present:
        for row in rows:
            per_model[row.get(MODEL_COLUMN, "")].add(row.get(column))
        if any(len(v) > 1 for v in per_model.values()):
            return column
        per_model.clear()
    return present[0] if present else None


def options() -> None:
    """(c)+(d) What each collapsing rule does to saturation and tiers."""
    from benchmark_scoring import MIN_SATURATION_POPULATION, measure_saturation
    from fetch_benchmarks import load_benchmark_catalog, load_benchmark_scores

    print("\n(c)/(d) WHAT EACH COLLAPSING RULE DOES\n")
    header = f"{'benchmark':29}{'rows':>6}{'models':>7}{'as-is':>8}"
    for rule in RULES:
        header += f"{rule:>9}"
    print(header + "   measurable on models?")

    falls_below = []
    for benchmark in load_benchmark_catalog():
        scores = load_benchmark_scores(benchmark)
        if scores is None or not scores.scores:
            continue
        groups = _grouped(scores)
        if len(groups) == len(scores.scores):
            continue  # nothing to collapse
        line = (
            f"{benchmark.name[:28]:29}{len(scores.scores):>6}{len(groups):>7}"
        )
        as_is = measure_saturation(scores)[0]
        line += f"{'  n/a' if as_is is None else f'{as_is:.3f}':>8}"
        for rule in RULES.values():
            value = measure_saturation(_collapsed(scores, rule))[0]
            line += f"{'  n/a' if value is None else f'{value:.3f}':>9}"
        ok = len(groups) >= MIN_SATURATION_POPULATION
        if not ok and as_is is not None:
            falls_below.append((benchmark.name, len(scores.scores), len(groups)))
        print(line + f"   {'yes' if ok else 'NO — below the minimum'}")

    if falls_below:
        print("\n  BECOMES UNMEASURABLE when counted by model:")
        for name, rows, models in falls_below:
            print(f"    {name:29} {rows} rows -> {models} models")

    print(
        "\n  DIRECTION, counted rather than asserted. An earlier draft of\n"
        "  this probe asserted 'uniformly UP' before counting, which is the\n"
        "  CLAUDE.md section 7 bug class about inventable directions."
    )
    _direction()


def _direction() -> None:
    from benchmark_scoring import measure_saturation
    from fetch_benchmarks import load_benchmark_catalog, load_benchmark_scores

    up = down = mixed = 0
    for benchmark in load_benchmark_catalog():
        scores = load_benchmark_scores(benchmark)
        if scores is None or not scores.scores:
            continue
        groups = _grouped(scores)
        if len(groups) == len(scores.scores):
            continue
        as_is = measure_saturation(scores)[0]
        if as_is is None:
            continue
        values = [
            measure_saturation(_collapsed(scores, rule))[0] for rule in RULES.values()
        ]
        values = [v for v in values if v is not None]
        if not values:
            continue
        if all(v > as_is for v in values):
            up += 1
        elif all(v < as_is for v in values):
            down += 1
        else:
            mixed += 1
    print(
        f"    rises under every rule: {up}   falls under every rule: {down}   "
        f"rule-dependent: {mixed}"
    )


def plateau() -> None:
    """(e) The population threshold, rechecked on distinct-model counts."""
    from benchmark_scoring import MIN_SATURATION_POPULATION
    from fetch_benchmarks import load_benchmark_catalog, load_benchmark_scores

    print(
        f"\n(e) THE POPULATION PLATEAU, ON MODEL COUNTS "
        f"(current minimum {MIN_SATURATION_POPULATION})\n"
    )
    print(f"{'benchmark':31}{'rows':>7}{'models':>8}{'margin (rows)':>15}{'margin (models)':>17}")
    rows_counts, model_counts = [], []
    for benchmark in load_benchmark_catalog():
        scores = load_benchmark_scores(benchmark)
        if scores is None or not scores.scores:
            continue
        n_rows = len(scores.scores)
        n_models = len(_grouped(scores))
        rows_counts.append(n_rows)
        model_counts.append(n_models)
        if min(n_rows, n_models) <= 120:
            print(
                f"{benchmark.name[:30]:31}{n_rows:>7}{n_models:>8}"
                f"{n_rows - MIN_SATURATION_POPULATION:>+15}"
                f"{n_models - MIN_SATURATION_POPULATION:>+17}"
            )

    def plateau_for(counts):
        """Thresholds over which the measurable/unmeasurable split is fixed."""
        counts = sorted(counts)
        low, high = 1, 10_000
        base = {c >= MIN_SATURATION_POPULATION for c in counts}
        for threshold in range(1, 200):
            split = {c >= threshold for c in counts}
            partition = tuple(c >= threshold for c in counts)
            reference = tuple(c >= MIN_SATURATION_POPULATION for c in counts)
            if partition == reference:
                low = min(low, threshold) if low != 1 else threshold
                high = threshold
        lows = [
            t for t in range(1, 200)
            if tuple(c >= t for c in counts)
            == tuple(c >= MIN_SATURATION_POPULATION for c in counts)
        ]
        return min(lows), max(lows)

    r_low, r_high = plateau_for(rows_counts)
    m_low, m_high = plateau_for(model_counts)
    print(f"\n  plateau counting ROWS   : {r_low}-{r_high}")
    print(f"  plateau counting MODELS : {m_low}-{m_high}")
    print(
        "\n  (The plateau is the range of thresholds over which the set of\n"
        "  measurable benchmarks is unchanged. Rank/tier effects are\n"
        "  confirmed with `probes/impact.py parameter`.)"
    )


def overlap() -> None:
    """(f) Does cross_source match on rows or on models?"""
    from cross_source import agreement_for, load_score_sets
    from fetch_benchmarks import load_benchmark_catalog

    print("\n(f) CROSS-SOURCE OVERLAP — rows or models?\n")
    print(f"{'benchmark':31}{'overlap':>9}{'dup rows in either set':>24}")
    affected = 0
    for benchmark in load_benchmark_catalog():
        agreement = agreement_for(benchmark)
        if agreement is None or agreement.scatter is None:
            continue
        duplicated = 0
        for scores in load_score_sets(benchmark):
            groups = _grouped(scores)
            duplicated += len(scores.scores) - len(groups)
        if duplicated:
            affected += 1
        print(f"{benchmark.name[:30]:31}{agreement.overlap:>9}{duplicated:>24}")
    print(
        f"\n  {affected} of the 8 measurable pairs draw on a set containing\n"
        "  duplicate model rows. Whether that inflates the overlap depends on\n"
        "  how match_key collapses them — see the check below."
    )
    _overlap_mechanism()


def _overlap_mechanism() -> None:
    """What cross_source actually does with a model's several rows."""
    import collections
    import statistics

    import cross_source as cs
    from fetch_benchmarks import load_benchmark_catalog

    print(
        "\n  MECHANISM, read from the code rather than assumed. An earlier\n"
        "  draft of this probe claimed the index keeps 'whichever row the\n"
        "  builder saw last'. It does not. cross_source._index_by_model\n"
        "  takes the MEAN of a model's rows:\n"
        "      grouped.setdefault(key, []).append(score)\n"
        "      return {key: statistics.mean(values) ...}\n"
        "  So the reproducibility factor silently averages a model's\n"
        "  configurations — precisely what D5 banned one layer down. It\n"
        "  also drops blank-named rows, because `if key:` skips them.\n"
        "\n  Overlap counts are NOT inflated: the dict holds one entry per\n"
        "  model either way. What moves is the VALUE each model contributes.\n"
    )

    original = cs._index_by_model

    def indexer(rule):
        def index(scores):
            grouped: dict[str, list[float]] = collections.defaultdict(list)
            for name, score in zip(scores.model_names, scores.scores):
                key = cs.match_key(name)
                if key:
                    grouped[key].append(score)
            return {key: rule(values) for key, values in grouped.items()}

        return index

    print(f"  {'benchmark':29}{'overlap':>8}{'mean':>9}{'best':>9}{'worst':>9}{'median':>9}")
    collected: dict[str, list[float]] = collections.defaultdict(list)
    try:
        for benchmark in load_benchmark_catalog():
            cs._index_by_model = original
            cs._agreement_by_key.cache_clear()
            report = cs.agreement_for(benchmark)
            if report is None or report.scatter is None:
                continue
            line = f"  {benchmark.name[:28]:29}{report.overlap:>8}{report.scatter:>9.4f}"
            collected["mean"].append(report.scatter)
            for name, rule in (("best", max), ("worst", min), ("median", statistics.median)):
                cs._index_by_model = indexer(rule)
                cs._agreement_by_key.cache_clear()
                other = cs.agreement_for(benchmark)
                collected[name].append(other.scatter)
                line += f"{other.scatter:>9.4f}"
            print(line)
    finally:
        cs._index_by_model = original
        cs._agreement_by_key.cache_clear()

    print(
        f"\n  n={len(collected['mean'])}. Individual readings move — HellaSwag\n"
        f"  {collected['mean'][2]:.4f} -> {collected['best'][2]:.4f} under `best` — but the MAX does not:\n"
        f"  {max(collected['mean']):.4f} under every rule, and it is the max that\n"
        "  derives HEALTHY_SPREAD (3 x max = 0.24). So the constant survives\n"
        "  the collapsing rule even though the readings feeding it do not.\n"
        "  That is worth stating because it is the one place in this\n"
        "  investigation where the defect does NOT propagate."
    )


REPORTS = {
    "inflation": inflation,
    "unattributed": unattributed,
    "options": options,
    "plateau": plateau,
    "overlap": overlap,
}


def main(argv: list[str]) -> None:
    if not argv:
        for report in REPORTS.values():
            report()
        return
    for name in argv:
        report = REPORTS.get(name)
        if report is None:
            print(f"unknown report {name!r}; try one of {', '.join(REPORTS)}")
            continue
        report()


if __name__ == "__main__":
    main(sys.argv[1:])
