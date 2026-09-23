"""
Smoke tests for every command a document cites as evidence.

WHY THIS FILE EXISTS. `backtest.py --sweep` — the command CLAUDE.md
section 4a names as the project's headline diagnostic — raised
ZeroDivisionError for 28 commits, from e247226 until 2026-09-22. Nothing
went red, because the suite never invoked it. The single-factor
comparison and the release-date baseline print after the crash point, so
the one diagnostic that asks whether the scorer beats a calendar
silently stopped running, and four figures in the brief drifted in the
dark while it was dead.

This is the same failure mode CLAUDE.md section 6 already warned about
for the fetchers ("CI runs OFFLINE against committed data ... the suite
will stay green"), arriving somewhere nobody had guarded.

WHAT THESE TESTS ASSERT, and what they deliberately do not. They assert
that each command RUNS, exits zero, and produces the sections it is
cited for. They do NOT assert specific numbers — that is
tests/test_doc_figures.py's job, and mixing the two would mean a
legitimate data update breaks a liveness check. A diagnostic that
crashes and a diagnostic whose output moved are different failures and
should fail differently.

Each command runs in a subprocess, because that is how a reader runs it.
An in-process import would not have caught the sweep crash, which came
from module-level weight mutation.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

# Every command cited as evidence in README.md, CLAUDE.md or docs/*.md,
# with the sections its output must contain. Keep this in step with
# test_docs_cite_only_covered_commands below, which fails if a document
# starts citing something absent from here.
COMMANDS: list[tuple[list[str], tuple[str, ...]]] = [
    (["backtest.py"], ("RETIREMENT TEST", "Confusion matrix", "TRAJECTORY")),
    (
        ["backtest.py", "--sweep"],
        (
            "RETIREMENT TEST",
            "SINGLE-FACTOR",
            "release date alone",  # the baseline that vanished in the crash
            "SENSITIVITY",
        ),
    ),
    (["probes/findings.py"], ("HUMANEVAL", "COVERAGE", "MODEL SIDE")),
    (["probes/findings.py", "humaneval"], ("HUMANEVAL", "contamination")),
    (["probes/findings.py", "coverage"], ("COVERAGE", "populations")),
    (["probes/findings.py", "backtest"], ("BACKTEST", "valid (same tier)")),
    (["probes/findings.py", "candidate1"], ("CANDIDATE 1", "SWE-Bench Verified")),
    (["probes/findings.py", "noise"], ("SCATTER", "HEALTHY_SPREAD")),
    (["probes/findings.py", "cliff"], ("POPULATION CLIFF", "threshold")),
    (["probes/findings.py", "modelside"], ("MODEL SIDE", "repeated labels")),
    (["probes/findings.py", "correlations"], ("PREDICTS THE RETIREMENT", "r(age, kept)")),
    (["probes/findings.py", "decay"], ("HEALTH DECAY", "per day")),
    (["probes/config_rows.py"], ("CONFIGURATION ROWS", "DIRECTION, counted")),
    (["probes/hindcast.py"], ("HINDCAST", "discordant pairs", "RECORDED")),
    (["probes/impact.py"], ("FULL", "PARTIAL", "THIN", "citations")),
    (["probes/impact.py", "tiers"], ("FULL", "PARTIAL", "THIN")),
    (["probes/impact.py", "citations"], ("benchmark cited", "in catalog?")),
    (["probes/impact.py", "weights"], ("evidence tier", "total weight")),
    (
        ["probes/impact.py", "parameter", "HEALTHY_SPREAD",
         "0.084", "0.197", "0.24", "0.358"],
        ("HEALTHY_SPREAD", "rank moves", "mean health"),
    ),
    (
        ["probes/impact.py", "parameter", "MIN_SATURATION_POPULATION",
         "20", "25", "30", "35", "40"],
        ("MIN_SATURATION_POPULATION", "tier changes"),
    ),
    (["probes/musr_baseline.py"], ("COMMITTED", "random_baseline")),
]

# Commands cited in documents that CANNOT be smoke-tested here, each with
# the reason. Anything added to this list is a gap in the guarantee and
# has to justify itself.
UNCOVERABLE = {
    "fetch_models.py": "hundreds of Hub requests; CI is offline (CLAUDE.md section 6)",
    "fetch_benchmark_scores.py": "fetches HF leaderboards and EvalPlus; CI is offline",
    "enrich_scores.py": "needs ARTIFICIAL_ANALYSIS_API_KEY and the network",
    "app.py": "starts a long-lived Gradio server; imported by test_app_imports instead",
    "probes/gsm1k_effect.py": "downloads arXiv 2405.00332 and parses it; network",
    "probes/arc_agi_population.py": (
        "lists a 75-directory HF dataset; network, and nothing to vendor"
    ),
}


def _run(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=300,
    )


@pytest.mark.parametrize(
    "args,expected",
    COMMANDS,
    ids=[" ".join(args) for args, _ in COMMANDS],
)
def test_cited_command_runs(args: list[str], expected: tuple[str, ...]) -> None:
    """
    The command exits zero and prints the sections it is cited for.

    A non-zero exit is the sweep crash. A missing section is the subtler
    version of it: the command still "works" while the part a document
    quotes has stopped being produced.
    """
    result = _run(args)
    assert result.returncode == 0, (
        f"`python {' '.join(args)}` exited {result.returncode}\n"
        f"--- stderr ---\n{result.stderr[-3000:]}"
    )
    for section in expected:
        assert section in result.stdout, (
            f"`python {' '.join(args)}` ran but did not print {section!r}. "
            "The command is cited for that output.\n"
            f"--- stdout ---\n{result.stdout[-2000:]}"
        )


def test_app_imports() -> None:
    """app.py cannot be run in CI, but it can be imported."""
    result = _run(["-c", "import app"])
    assert result.returncode == 0, result.stderr[-2000:]


def test_every_probe_has_a_smoke_test() -> None:
    """
    A probe added without being run here is the sweep bug waiting again.
    """
    covered = {args[0] for args, _ in COMMANDS} | set(UNCOVERABLE)
    on_disk = {
        f"probes/{p.name}" for p in (ROOT / "probes").glob("*.py")
    }
    missing = on_disk - covered
    assert not missing, (
        f"probes with no smoke test and no stated reason: {sorted(missing)}. "
        "Add it to COMMANDS, or to UNCOVERABLE with why."
    )


def test_docs_cite_only_covered_commands() -> None:
    """
    Every `python <script>` invocation in a document is either smoke
    tested or listed as uncoverable with a reason.

    This is the guarantee itself: a document cannot start citing a
    command as evidence without that command being run by CI.
    """
    import re

    covered = {args[0] for args, _ in COMMANDS} | set(UNCOVERABLE)
    pattern = re.compile(r"python\s+((?:probes/)?[A-Za-z0-9_./-]+\.py)")
    uncovered: dict[str, set[str]] = {}
    docs = [ROOT / "README.md", ROOT / "CLAUDE.md", *sorted((ROOT / "docs").glob("*.md"))]
    for doc in docs:
        for script in pattern.findall(doc.read_text()):
            if script not in covered:
                uncovered.setdefault(script, set()).add(doc.name)
    assert not uncovered, (
        "documents cite commands that CI never runs: "
        + "; ".join(f"{s} (in {', '.join(sorted(d))})" for s, d in sorted(uncovered.items()))
        + ". Add each to COMMANDS, or to UNCOVERABLE with the reason."
    )
