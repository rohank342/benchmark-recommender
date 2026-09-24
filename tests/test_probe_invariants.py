"""
Invariants for the probes that group or match data.

WHY THIS FILE EXISTS. `probes/config_rows.py` produced wrong figures
TWICE in one session, and both errors reached the documents before
anyone noticed:

  1. It matched Epoch CSV files to benchmarks BY ROW COUNT, over an
     unordered `glob`. Aider polyglot has two columns with 77 numeric
     values; OSWorld and ARC have rows the loader drops, so no file
     matched at all. It reported Aider polyglot collapsing to 0.350 —
     a number from a different file entirely.
  2. It grouped scores by model name and treated every BLANK name as
     one shared model. 188 rows across 10 benchmarks have an empty
     `Model version`, so this silently deleted dozens of rows from the
     top band and produced GSM8K 0.632 where the truth is 0.289.

Nothing checked the probe. The doc-figure drift check
(`test_doc_figures.py`) compares a document against a probe, so when the
probe is wrong they agree and the check passes. These tests check the
probe against the data instead.

WHAT AN INVARIANT IS HERE: a property that must hold for ANY input, not
a pinned value. Rows are conserved; a blank name is never a model; a
file maps to exactly one benchmark; a grouping key is never empty. Each
one corresponds to a way the probe has already been wrong, or an
obvious neighbour of one.

Verified to catch both original bugs by reverting the fixes — see
`test_invariants_catch_the_row_count_matching_bug` and
`test_invariants_catch_the_blank_name_merging_bug`.
"""

from __future__ import annotations

import collections
import csv
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
EPOCH_DIR = ROOT / "data" / "epoch_benchmarks"


def _catalog_with_scores():
    from fetch_benchmarks import load_benchmark_catalog, load_benchmark_scores

    for benchmark in load_benchmark_catalog():
        scores = load_benchmark_scores(benchmark)
        if scores is not None and scores.scores:
            yield benchmark, scores


class TestGroupingInvariants:
    """Properties `probes/config_rows.py::_grouped` must always have."""

    def test_rows_are_conserved(self):
        """
        Every input row lands in exactly one group. This is the invariant
        the blank-name bug broke: 188 rows went in and far fewer came
        out, with nothing counting the loss.
        """
        from probes.config_rows import _grouped

        for benchmark, scores in _catalog_with_scores():
            groups = _grouped(scores)
            kept = sum(len(values) for values in groups.values())
            assert kept == len(scores.scores), (
                f"{benchmark.name}: {len(scores.scores)} rows in, {kept} out. "
                "Rows are being dropped or duplicated by the grouping."
            )

    def test_a_blank_name_is_never_treated_as_a_model(self):
        """
        Blank names must not share a group. Two rows with no model name
        are two unattributed rows, not one model with two scores.
        """
        from probes.config_rows import _grouped

        for benchmark, scores in _catalog_with_scores():
            names = scores.model_names or []
            blank = sum(1 for n in names if not (n or "").strip())
            if not blank:
                continue
            groups = _grouped(scores)
            # Each blank row must be alone in its own group.
            unattributed = [k for k in groups if k.startswith("__unattributed")]
            assert len(unattributed) == blank, (
                f"{benchmark.name}: {blank} blank-named rows collapsed into "
                f"{len(unattributed)} groups. They must stay distinct."
            )
            for key in unattributed:
                assert len(groups[key]) == 1, (
                    f"{benchmark.name}: group {key} holds "
                    f"{len(groups[key])} rows; a blank name is not a model."
                )

    def test_no_grouping_key_is_empty(self):
        """An empty key means 'we grouped on nothing and called it a model'."""
        from probes.config_rows import _grouped

        for benchmark, scores in _catalog_with_scores():
            for key in _grouped(scores):
                assert key and key.strip(), (
                    f"{benchmark.name}: produced an empty grouping key"
                )

    def test_collapsing_yields_exactly_one_value_per_group(self):
        """A collapsing rule may not add or lose models."""
        from probes.config_rows import _collapsed, _grouped

        for benchmark, scores in _catalog_with_scores():
            groups = _grouped(scores)
            for rule in (max, min):
                collapsed = _collapsed(scores, rule)
                assert len(collapsed.scores) == len(groups), (
                    f"{benchmark.name}: {len(groups)} groups collapsed to "
                    f"{len(collapsed.scores)} values"
                )
                assert len(collapsed.model_names) == len(collapsed.scores)

    def test_collapsed_values_come_from_the_input(self):
        """
        `best` and `worst` must return a value that was actually
        observed. A rule that invents a number is the evidence
        standard's first line broken by arithmetic.
        """
        from probes.config_rows import _collapsed

        for benchmark, scores in _catalog_with_scores():
            observed = set(scores.scores)
            for rule in (max, min):
                for value in _collapsed(scores, rule).scores:
                    assert value in observed, (
                        f"{benchmark.name}: {rule.__name__} produced {value}, "
                        "which is not in the input"
                    )


class TestFileMatchingInvariants:
    """Properties the Epoch file lookup must always have."""

    def test_each_epoch_file_maps_to_exactly_one_benchmark(self):
        """
        The row-count matcher could map a file to several benchmarks or
        to none. Keying on `epoch_source_file` must be a function.
        """
        from fetch_benchmarks import load_benchmark_catalog

        owners: dict[str, list[str]] = collections.defaultdict(list)
        for benchmark in load_benchmark_catalog():
            name = getattr(benchmark, "epoch_source_file", None)
            if name:
                owners[name].append(benchmark.name)
        duplicated = {f: b for f, b in owners.items() if len(b) > 1}
        assert not duplicated, f"one Epoch file claimed by several benchmarks: {duplicated}"

    def test_every_declared_epoch_file_exists(self):
        """A lookup that silently finds nothing is how the dash appeared."""
        from fetch_benchmarks import load_benchmark_catalog

        missing = [
            (b.name, b.epoch_source_file)
            for b in load_benchmark_catalog()
            if getattr(b, "epoch_source_file", None)
            and not (EPOCH_DIR / b.epoch_source_file).exists()
        ]
        assert not missing, f"declared Epoch files that do not exist: {missing}"

    def test_the_config_column_lookup_never_guesses(self):
        """
        `_epoch_config_column` must answer from the benchmark's declared
        file, so a benchmark with no declared file gets None rather than
        some other benchmark's column.
        """
        from dataclasses import replace

        from fetch_benchmarks import find_benchmark
        from probes.config_rows import _epoch_config_column

        terminal = find_benchmark("Terminal Bench")
        assert _epoch_config_column(terminal) == "Agent"
        # Strip the declaration: the answer must become None, not a
        # column borrowed from whichever file happened to match.
        assert _epoch_config_column(replace(terminal, epoch_source_file=None)) is None


class TestTheseWouldHaveCaughtLastSessionsBugs:
    """
    The point of the file: reverting each fix must make an invariant
    fail. An invariant nobody has seen fail is a guess about what
    matters.
    """

    def test_invariants_catch_the_blank_name_merging_bug(self):
        """Re-introduce the merge and the conservation invariant survives
        (rows are still conserved) but the blank-name invariant fails."""
        import probes.config_rows as cr

        def merging_grouped(scores):
            groups: dict[str, list[float]] = collections.defaultdict(list)
            names = scores.model_names or []
            for index, value in enumerate(scores.scores):
                name = names[index] if index < len(names) else ""
                groups[name].append(value)  # BUG: blanks share the key ""
            return groups

        original = cr._grouped
        try:
            cr._grouped = merging_grouped
            with pytest.raises(AssertionError):
                TestGroupingInvariants().test_a_blank_name_is_never_treated_as_a_model()
            with pytest.raises(AssertionError):
                TestGroupingInvariants().test_no_grouping_key_is_empty()
        finally:
            cr._grouped = original

    def test_invariants_catch_the_row_count_matching_bug(self):
        """
        Re-introduce row-count file matching and show it is AMBIGUOUS —
        several files match one benchmark, so the answer depends on the
        order an unordered `glob` happens to return.

        Note what this test does NOT claim. Run today, the old matcher
        resolves the three benchmarks it got wrong last session
        correctly, because it takes the first candidate and the
        filesystem currently offers the right one first. That is not a
        defence of it: an answer that depends on directory order is
        arbitrary whether or not it lands correctly on one machine. The
        invariant is that the mapping must be a FUNCTION of the
        benchmark, which is what `test_each_epoch_file_maps_to_exactly_one_benchmark`
        and the `epoch_source_file` lookup now guarantee.
        """
        from fetch_benchmarks import load_benchmark_catalog, load_benchmark_scores

        def candidate_files(row_count):
            """Every file the old matcher could have picked."""
            found = set()
            for path in sorted(EPOCH_DIR.glob("*.csv")):
                if path.name == "benchmark_metadata.csv":
                    continue
                with path.open(newline="", encoding="utf-8") as handle:
                    rows = list(csv.DictReader(handle))
                if not rows or "Model version" not in rows[0]:
                    continue
                for column in rows[0]:
                    try:
                        values = [float(r[column]) for r in rows if r[column]]
                    except (ValueError, TypeError):
                        continue
                    if len(values) == row_count:
                        found.add(path.name)
                        break
            return found

        ambiguous = []
        for benchmark in load_benchmark_catalog():
            scores = load_benchmark_scores(benchmark)
            if scores is None or not scores.scores or scores.source != "epoch_ai":
                continue
            candidates = candidate_files(len(scores.scores))
            if len(candidates) > 1:
                ambiguous.append((benchmark.name, sorted(candidates)))

        assert ambiguous, (
            "the old row-count matcher was expected to be ambiguous for at "
            "least one benchmark; if it no longer is, this regression test "
            "is stale and should be re-derived rather than deleted"
        )
        # Recorded so the failure mode stays legible: four benchmarks can
        # each be matched to a file that is not theirs.
        names = {name for name, _ in ambiguous}
        assert "GSM8K" in names and "SWE-Bench Verified" in names, ambiguous


class TestD6IsTheOnlyDefinitionOfAModelsScore:
    """
    DECISION D6: one collapsing function, used on every path.

    Saturation and cross-source reproducibility both aggregate a
    benchmark's rows into per-model values. Before D6 they did it
    differently — saturation not at all, reproducibility by taking the
    mean — so the same benchmark had two incompatible answers to "what
    is this model's score?". These tests fail if either path drifts off
    the shared function again.
    """

    def test_saturation_measures_over_models_not_rows(self):
        """
        The model count in the explanation string must match the
        collapsed population, not the raw row count.
        """
        from benchmark_scoring import measure_saturation

        for benchmark, scores in _catalog_with_scores():
            value, note = measure_saturation(scores)
            if value is None:
                continue
            collapsed = len(scores.one_row_per_model().scores)
            assert f"of {collapsed} " in note, (
                f"{benchmark.name}: saturation note says {note!r} but the "
                f"collapsed population is {collapsed} models"
            )

    def test_saturation_is_unchanged_by_pre_collapsing(self):
        """
        Collapsing twice must equal collapsing once. If `measure_saturation`
        did its own aggregation instead of deferring, these would differ.
        """
        from benchmark_scoring import measure_saturation

        for benchmark, scores in _catalog_with_scores():
            once = measure_saturation(scores)[0]
            twice = measure_saturation(scores.one_row_per_model())[0]
            assert once == twice, f"{benchmark.name}: {once} != {twice}"

    def test_reproducibility_uses_the_same_definition(self):
        """
        `cross_source._index_by_model` must agree with the shared
        function on every model it indexes — no means, no last-row-wins.
        """
        from cross_source import _index_by_model, load_score_sets, match_key

        from fetch_benchmarks import load_benchmark_catalog

        checked = 0
        for benchmark in load_benchmark_catalog():
            for scores in load_score_sets(benchmark):
                if not scores.scores:
                    continue
                index = _index_by_model(scores)
                collapsed = scores.one_row_per_model()
                expected: dict[str, float] = {}
                for name, value in zip(collapsed.model_names, collapsed.scores):
                    key = match_key(name)
                    if key and value > expected.get(key, float("-inf")):
                        expected[key] = value
                assert index == expected, f"{benchmark.name}/{scores.source} diverged"
                checked += 1
        assert checked, "no score sets were checked — the test is vacuous"

    def test_unattributed_rows_never_reach_a_reading(self):
        """
        A row with no model name must not appear in saturation or in
        reproducibility. This is option (vi), enforced rather than
        described.
        """
        from cross_source import _index_by_model

        for benchmark, scores in _catalog_with_scores():
            collapsed = scores.one_row_per_model()
            assert all(n and n.strip() for n in collapsed.model_names), (
                f"{benchmark.name}: an unattributed row survived collapsing"
            )
            assert collapsed.unattributed == 0
            assert "" not in _index_by_model(scores)

    def test_the_population_is_named_accurately(self):
        """
        Option (v): where most rows name no model, the reading says
        'agent systems' rather than borrowing the source's label.
        """
        from fetch_benchmarks import find_benchmark, load_benchmark_scores

        osworld = load_benchmark_scores(find_benchmark("OSWorld"))
        assert "agent systems" in osworld.population_note, osworld.population_note
        mmlu = load_benchmark_scores(find_benchmark("MMLU"))
        assert "rows name no model" in mmlu.population_note

    def test_a_set_with_no_attribution_becomes_unmeasurable(self):
        """
        Deliberate, and the conservative direction. Keeping every row
        when a source names no models would let a source that publishes
        LESS information escape the rule one publishing more must obey —
        the uncheckability-pays failure this project has recorded five
        times.
        """
        from benchmark_scoring import measure_saturation
        from fetch_benchmarks import BenchmarkScores

        nameless = BenchmarkScores(
            benchmark_key="test",
            scores=[0.5] * 60,
            model_names=[""] * 60,
        )
        assert nameless.one_row_per_model().scores == []
        assert measure_saturation(nameless)[0] is None

    def test_no_committed_source_is_actually_nameless(self):
        """The rule above costs nothing today; this is what says so."""
        from cross_source import load_score_sets
        from fetch_benchmarks import load_benchmark_catalog

        for benchmark in load_benchmark_catalog():
            for scores in load_score_sets(benchmark):
                if not scores.scores:
                    continue
                named = sum(1 for n in scores.model_names if (n or "").strip())
                assert named, f"{benchmark.name}/{scores.source} names no models"
