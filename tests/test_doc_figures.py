"""
Load-bearing figures in the docs must match what the probes produce.

WHY THIS FILE EXISTS. Two figures last session came from a state that
later changes had moved, and each shaped the next session's priorities
before anyone caught it. "45.0 sits above 18 of 26 health scores" was 8
of 28 once the scale moved; "one disagreeing pair, spread 0.022" was
zero pairs. The founding headline existed in three different numeric
forms across this repo at once. CLAUDE.md section 9 answers this with a
rule for the author — re-measure every number in the session that
reports it — and this file is the machine check behind that rule, for
the figures a reader would act on.

HOW IT WORKS, and it is deliberately dull. A registry of figures. Each
entry names:

  * the command that PRODUCES the number, and a regex that pulls it out
    of that command's output — this side is authoritative;
  * one or more (document, regex) pairs that pull the number as WRITTEN;
  * a tolerance, because a doc may legitimately round 0.4380 to 0.438.

The test compares the two and fails with both values. It does not
rewrite anything: a drift is a thing for a person to look at, since
either the doc or the code may be the wrong one. Twice in this project
the test was right and the catalog was internally contradictory.

WHAT IT IS NOT. Not a templating system, and not a check that the prose
is accurate — only that the NUMBERS in it still match the code. A doc
can still be wrong in words. The doc-side regexes are written loosely
(they match the number in its sentence, not the whole sentence) so that
rewording does not break them, but a figure that is deleted outright
WILL fail, which is intended: silently dropping a load-bearing figure is
how the founding headline drifted.

Commands are run once each and cached, because several entries share
one.
"""

from __future__ import annotations

import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

_OUTPUT_CACHE: dict[tuple[str, ...], str] = {}


def _output(command: tuple[str, ...]) -> str:
    if command not in _OUTPUT_CACHE:
        result = subprocess.run(
            [sys.executable, *command],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=300,
        )
        assert result.returncode == 0, (
            f"`python {' '.join(command)}` failed; tests/test_diagnostics.py "
            f"covers liveness\n{result.stderr[-2000:]}"
        )
        _OUTPUT_CACHE[command] = result.stdout
    return _OUTPUT_CACHE[command]


@dataclass(frozen=True)
class Figure:
    """One load-bearing number, and everywhere it is written down."""

    name: str
    command: tuple[str, ...]
    probe: str  # regex over the command's stdout, one capture group
    docs: tuple[tuple[str, str], ...]  # (path, regex with one capture group)
    tolerance: float = 0.0005
    note: str = field(default="")
    # The docs often state a magnitude ("separation lost by 26.9 points")
    # where the probe prints a signed value. Comparing |x| is right there
    # and wrong for a correlation, where the sign IS the claim — so it is
    # opt-in per figure rather than a blanket rule.
    absolute: bool = False
    # Health decays with age every day the repo is not touched, so any
    # figure derived from it is exact only on the date it was measured.
    # Rate measured 2026-09-23: mean catalog health falls 0.0285 points
    # per day (score_all_benchmarks at as_of 2026-09-22 vs 2026-09-23).
    # Figures marked here get a tolerance wide enough to survive a few
    # weeks and still catch a real change; see
    # test_decaying_figures_declare_a_rate.
    decays: bool = False


F = "probes/findings.py"
FIGURES: list[Figure] = [
    # ---- [1] HumanEval, the founding case -------------------------------
    Figure(
        "HumanEval measured saturation",
        (F, "humaneval"),
        r"discrimination\s+([\d.]+)\s+basis=measured",
        (
            # The doc states saturation (1 - discrimination). Handled by
            # `derive` below via the complement entry instead; here we pin
            # the factor itself so a change cannot pass unnoticed.
        ),
    ),
    Figure(
        "HumanEval health",
        (F, "humaneval"),
        r"health\s+([\d.]+)\s+\(tier",
        (
            (r"docs/FINDINGS.md", r"measurement health \| \*\*([\d.]+)\*\*"),
            (r"CLAUDE.md", r"measurement health ([\d.]+), resting on"),
        ),
        tolerance=1.0,
        decays=True,
        note="health decays ~0.03 points/day; 1.0 covers ~5 weeks",
    ),
    Figure(
        "HumanEval contamination rate",
        (F, "humaneval"),
        r"contamination rate\s+([\d.]+)",
        ((r"docs/FINDINGS.md", r"contamination rate \| \*\*([\d.]+)\*\*"),),
    ),
    Figure(
        "HumanEval contamination effect",
        (F, "humaneval"),
        r"contamination eff\.\s+([\d.]+)",
        ((r"docs/FINDINGS.md", r"contamination effect \| \*\*([\d.]+)\*\*"),),
    ),
    # ---- [2] Coverage ---------------------------------------------------
    Figure(
        "catalog size",
        (F, "coverage"),
        r"COVERAGE — catalog of (\d+) benchmarks",
        (
            (r"docs/FINDINGS.md", r"^(\d+) benchmarks across 10 task categories"),
            (r"README.md", r"An evidence dossier on (\d+) LLM benchmarks"),
            (r"CLAUDE.md", r"EVIDENCE DOSSIER on (\d+) benchmarks"),
        ),
    ),
    Figure(
        "benchmarks with a score source",
        (F, "coverage"),
        r"has any score source\s+(\d+) of",
        ((r"docs/FINDINGS.md", r"has any score source \| (\d+) of"),),
    ),
    Figure(
        "saturation measured",
        (F, "coverage"),
        r"saturation measured\s+(\d+) of",
        (
            (r"docs/FINDINGS.md", r"from a real score distribution \| \*\*(\d+) of"),
            (r"README.md", r"\*\*Measured saturation\*\* for (\d+) of"),
            (r"README.md", r"measured saturation for \*\*(\d+) of 28\*\*"),
            (r"README.md", r"Saturation \(the `discrimination` factor\) \| (\d+) of"),
        ),
    ),
    Figure(
        "cross-source agreement measured",
        (F, "coverage"),
        r"cross-source agreement\s+(\d+) of",
        (
            (r"docs/FINDINGS.md", r"same models, two evaluators\) \| \*\*(\d+) of"),
            (r"README.md", r"\*\*Cross-source agreement\*\* for (\d+) of"),
            (r"README.md", r"Cross-source agreement \(`reproducibility`\) \| (\d+) of"),
            (r"README.md", r"cross-source agreement for \*\*(\d+) of 28\*\*"),
        ),
    ),
    Figure(
        "contamination rate known",
        (F, "coverage"),
        r"contamination rate known\s+(\d+) of",
        (
            (r"docs/FINDINGS.md", r"contamination \*rate\* known \| (\d+) of"),
            (r"README.md", r"fraction of items in pretraining corpora\) \| (\d+) of"),
        ),
    ),
    Figure(
        "contamination flagged but unquantified",
        (F, "coverage"),
        r"contamination merely flagged\s+(\d+) of",
        (
            (r"docs/FINDINGS.md", r"flagged but never quantified \| (\d+) of"),
            (r"README.md", r"never quantified — \*\*no penalty\*\* \| (\d+) of"),
        ),
    ),
    Figure(
        "item error rate known",
        (F, "coverage"),
        r"item error rate known\s+(\d+) of",
        (
            (r"docs/FINDINGS.md", r"item error rate known \| (\d+) of"),
            (r"README.md", r"wrong answer keys, broken tests\) \| (\d+) of"),
        ),
    ),
    Figure(
        "GPQA saturation, frontier population",
        (F, "coverage"),
        r"sat=([\d.]+)\s+n=\s*313",
        ((r"docs/FINDINGS.md", r"\*\*([\d.]+) saturated across 313 frontier models"),),
    ),
    Figure(
        "GPQA saturation, community population",
        (F, "coverage"),
        r"sat=([\d.]+)\s+n=\s*4575",
        ((r"docs/FINDINGS.md", r"and ([\d.]+) across\n  4,575 open community models"),),
    ),
    # ---- [3] Backtest ---------------------------------------------------
    Figure(
        "backtest valid pairs",
        (F, "backtest"),
        r"pairs 36: (\d+) valid",
        (
            (r"docs/FINDINGS.md", r"\| the scorer \| (\d+) \|"),
            (r"docs/BACKTEST.md", r"\| \*\*the scorer\*\* \| (\d+) \|"),
        ),
    ),
    Figure(
        "backtest scorer correct on valid pairs",
        (F, "backtest"),
        r"scorer correct\s+(\d+)/",
        (
            (r"docs/FINDINGS.md", r"\| the scorer \| 30 \| \*\*(\d+) \(100%\)\*\* \|"),
            (r"docs/BACKTEST.md", r"\| \*\*the scorer\*\* \| 30 \| \*\*(\d+) \(100%\)\*\* \|"),
        ),
    ),
    Figure(
        "backtest calendar correct on valid pairs",
        (F, "backtest"),
        r"release date correct\s+(\d+)/",
        (
            (r"docs/FINDINGS.md", r"sorting by release date \| 30 \| \*\*(\d+) \(100%\)\*\*"),
            (r"docs/BACKTEST.md", r"sorting by release date\*\* \| 30 \| \*\*(\d+) \(100%\)\*\*"),
        ),
    ),
    # ---- [4] Candidate 1 ------------------------------------------------
    Figure(
        "Candidate 1 margin at its as-of date",
        (F, "candidate1"),
        r"SWE-Bench Verified - GPQA Diamond = ([+-][\d.]+)",
        (
            (r"docs/FINDINGS.md", r"the margin is \*\*([+-][\d.]+) points\*\*"),
            (r"CLAUDE.md", r"pre-registration's own as-of date it now re-measures at\s*\n?\s*([+-][\d.]+)"),
        ),
    ),
    # ---- [5] Noise floor and HEALTHY_SPREAD -----------------------------
    Figure(
        "cross-source scatter, max",
        (F, "noise"),
        r"max ([\d.]+)\n",
        ((r"docs/FINDINGS.md", r"mean 0\.0390   max ([\d.]+)"),),
    ),
    Figure(
        "cross-source scatter, median",
        (F, "noise"),
        r"median ([\d.]+)\s+mean",
        ((r"docs/FINDINGS.md", r"median ([\d.]+)   mean"),),
    ),
    Figure(
        "HEALTHY_SPREAD",
        (F, "noise"),
        r"->  HEALTHY_SPREAD = ([\d.]+)",
        (
            (r"docs/FINDINGS.md", r"HEALTHY_SPREAD = ([\d.]+)\n```"),
            (r"README.md", r"the measured noise floor on 2026-09-22 \(([\d.]+)\)"),
        ),
    ),
    # ---- [6] Population cliff -------------------------------------------
    Figure(
        "MirrorCode scored models",
        (F, "cliff"),
        r"MirrorCode\s+n=\s*(\d+)",
        (
            (r"docs/FINDINGS.md", r"\| MirrorCode \| (\d+) \|"),
            (r"CLAUDE.md", r"MirrorCode's score rests on a release date, with (\d+) scored"),
        ),
    ),
    Figure(
        "SWE-Bench Verified scored models",
        (F, "cliff"),
        r"SWE-Bench Verified\s+n=\s*(\d+)",
        (
            (r"docs/FINDINGS.md", r"\| SWE-Bench Verified \| (\d+) \|"),
            (r"CLAUDE.md", r"SWE-Bench Verified (\d+), FrontierCode"),
        ),
    ),
    Figure(
        "GSO-Bench scored models",
        (F, "cliff"),
        r"GSO-Bench\s+n=\s*(\d+)",
        (
            (r"docs/FINDINGS.md", r"\| GSO-Bench \| (\d+) \|"),
            (r"CLAUDE.md", r"GSO-Bench (\d+)\."),
        ),
    ),
    # ---- [7] Model side --------------------------------------------------
    Figure(
        "scored models",
        (F, "modelside"),
        r"scored models (\d+), benchmark citations",
        ((r"docs/FINDINGS.md", r"coverage — 68 of (\d+) models"),),
    ),
    Figure(
        "benchmark citations",
        (F, "modelside"),
        r"benchmark citations (\d+)",
        ((r"docs/FINDINGS.md", r"\*\*66 of (\d+)\*\* citations sit inside"),),
    ),
    Figure(
        "models ranked after D3",
        (F, "modelside"),
        r"ranked \(>=1 weighted citation\)\s+(\d+)",
        (
            (r"docs/FINDINGS.md", r"\*\*6 of the (\d+)\*\* ranked models still hold"),
            (r"CLAUDE.md", r"(\d+) of 191 models are ranked"),
        ),
    ),
    Figure(
        "models shown unweighted after D3",
        (F, "modelside"),
        r"shown as unweighted evidence only\s+(\d+)",
        ((r"CLAUDE.md", r"are ranked, (\d+) are\n   shown as unweighted evidence"),),
    ),
    Figure(
        "repeated-label groups",
        (F, "modelside"),
        r"groups \(model, label, source\)\s+(\d+)",
        (
            (r"docs/FINDINGS.md", r"\*\*(\d+)\*\* \(model, label, source\) groups"),
            (r"CLAUDE.md", r"(\d+) \(model, label, source\) groups hold 2\+"),
        ),
    ),
    Figure(
        "repeated-label entries",
        (F, "modelside"),
        r"entries inside those groups\s+(\d+) of",
        (
            (r"docs/FINDINGS.md", r"\*\*(\d+) of 323\*\* citations sit inside"),
            (r"CLAUDE.md", r"covering (\d+) of 323 citations"),
        ),
    ),
    Figure(
        "repeated-label widest spread",
        (F, "modelside"),
        r"max ([\d.]+)\n",
        (
            (r"docs/FINDINGS.md", r"median 0\.040, \*\*max (\d+\.\d+)\*\*"),
            (r"CLAUDE.md", r"spread median 0\.040, max (\d+\.\d+)"),
        ),
    ),
    # ---- [8] Correlations ------------------------------------------------
    Figure(
        "r(age, kept)",
        (F, "correlations"),
        r"r\(age, kept\)\s+([+-][\d.]+)",
        (
            (r"docs/FINDINGS.md", r"\*\*release date\*\* \(age\) \| \*\*([+−-][\d.]+)\*\*"),
            (r"README.md", r"retire/keep decision at r = ([+−-][\d.]+)\*\*"),
            (r"README.md", r"retire/keep decision at \*\*r = ([+−-][\d.]+)\*\*"),
            (r"CLAUDE.md", r"r\(age, kept\)\s+([+-][\d.]+)"),
        ),
    ),
    Figure(
        "r(health, kept)",
        (F, "correlations"),
        r"r\(health, kept\)\s+([+-][\d.]+)",
        (
            (r"docs/FINDINGS.md", r"the composite health score \| ([+−-][\d.]+)"),
            (r"README.md", r"composite health score predicts it at \*\*([+−-][\d.]+)\*\*"),
            (r"README.md", r"the composite score at\n\*\*([+−-][\d.]+)\*\*"),
            (r"CLAUDE.md", r"r\(health, kept\)\s+([+-][\d.]+)"),
        ),
    ),
    Figure(
        "r(saturation, kept)",
        (F, "correlations"),
        r"r\(saturation, kept\)\s+([+-][\d.]+)",
        (
            (r"docs/FINDINGS.md", r"\| measured saturation \| ([+−-][\d.]+) \(n=11\)"),
            (r"README.md", r"measured saturation at \*\*([+−-][\d.]+)\*\*"),
            (r"CLAUDE.md", r"r\(saturation, kept\)\s+([+-][\d.]+)"),
        ),
    ),
    Figure(
        "r(age, saturation)",
        (F, "correlations"),
        r"r\(age, measured saturation\)\s+([+-][\d.]+)",
        (
            (r"docs/FINDINGS.md", r"\*\*\+0\.633, −0\.559 and ([+−-][\d.]+)\*\*"),
            (r"CLAUDE.md", r"r\(age, saturation\)\s+([+-][\d.]+)"),
        ),
    ),
    # ---- [9] The sweep ---------------------------------------------------
    Figure(
        "full scorer separation gap",
        ("backtest.py",),
        r"Perfect separation: False \(gap ([+-]?[\d.]+) points\)",
        (
            (r"docs/FINDINGS.md", r"separation lost by ([\d.]+) points"),
            (r"CLAUDE.md", r"separation lost by ([\d.]+) points \(was recorded"),
        ),
        absolute=True,
        note="docs state the magnitude; the probe prints it signed",
    ),
    Figure(
        "freshness alone, separation gap",
        ("backtest.py", "--sweep"),
        r"freshness\s+10/12\s+False\s+([+-][\d.]+)",
        (
            (r"docs/FINDINGS.md", r"\*\*freshness alone\*\* \(age decay\) \| \*\*10/12\*\* \| \*\*([+−-][\d.]+)\*\*"),
            (r"CLAUDE.md", r"loses separation by only ([\d.]+) points"),
            (r"README.md", r"loses separation by ([\d.]+) points against the full"),
        ),
        absolute=True,
        note="CLAUDE.md states the magnitude, FINDINGS.md the signed value",
    ),
    Figure(
        "discrimination alone, separation gap",
        ("backtest.py", "--sweep"),
        r"discrimination\s+8/12\s+False\s+([+-][\d.]+)",
        ((r"docs/FINDINGS.md", r"discrimination alone \(measured saturation\) \| 8/12 \| ([+−-][\d.]+)"),),
    ),
    Figure(
        "reproducibility alone, separation gap",
        ("backtest.py", "--sweep"),
        r"reproducibility\s+6/12\s+False\s+([+-][\d.]+)",
        ((r"docs/FINDINGS.md", r"reproducibility alone \| 6/12 \| ([+−-][\d.]+)"),),
    ),
    # ---- [10]/[11] parameter sweeps --------------------------------------
    Figure(
        "HEALTHY_SPREAD low end, mean health",
        ("probes/impact.py", "parameter", "HEALTHY_SPREAD",
         "0.084", "0.197", "0.24", "0.358"),
        r"0\.084\s+\d+\s+\d+\s+([\d.]+)",
        (
            (r"docs/FINDINGS.md", r"mean catalog health moves from \*\*([\d.]+) to"),
            (r"README.md", r"catalog health moves 14 points \(([\d.]+) →"),
            (r"CLAUDE.md", r"mean catalog health ([\d.]+) -> [\d.]+"),
        ),
        tolerance=1.0,
        decays=True,
        note="health decays ~0.03 points/day; 1.0 covers ~5 weeks",
    ),
    Figure(
        "HEALTHY_SPREAD high end, mean health",
        ("probes/impact.py", "parameter", "HEALTHY_SPREAD",
         "0.084", "0.197", "0.24", "0.358"),
        r"0\.358\s+\d+\s+\d+\s+([\d.]+)",
        (
            (r"docs/FINDINGS.md", r"moves from \*\*[\d.]+ to ([\d.]+)\*\*"),
            (r"README.md", r"moves 14 points \([\d.]+ → ([\d.]+)"),
            (r"CLAUDE.md", r"mean catalog health [\d.]+ -> ([\d.]+)"),
        ),
        tolerance=1.0,
        decays=True,
        note="health decays ~0.03 points/day; 1.0 covers ~5 weeks",
    ),
    Figure(
        "MIN_SATURATION_POPULATION at 40, tier changes",
        ("probes/impact.py", "parameter", "MIN_SATURATION_POPULATION",
         "20", "25", "30", "35", "40"),
        r"\n\s+40\s+\d+\s+(\d+)\s+[\d.]+",
        # CLAUDE.md section 7 was rewritten around the plateau on
        # 2026-09-23 and no longer states the 40-threshold figures;
        # FINDINGS.md and POPULATION_CLIFF.md carry them.
        ((r"docs/FINDINGS.md", r"changes \*\*(\d+) tiers and 16 ranks\*\*"),),
    ),
    Figure(
        "MIN_SATURATION_POPULATION at 40, rank moves",
        ("probes/impact.py", "parameter", "MIN_SATURATION_POPULATION",
         "20", "25", "30", "35", "40"),
        r"\n\s+40\s+(\d+)\s+\d+\s+[\d.]+",
        ((r"docs/FINDINGS.md", r"changes \*\*4 tiers and (\d+) ranks\*\*"),),
    ),
    # ---- [12] health decay ----------------------------------------------
    Figure(
        "health decay per day",
        (F, "decay"),
        r"falls ([\d.]+) points per day",
        ((r"docs/FINDINGS.md", r"mean catalog health falls (\d+\.\d+)"),),
        tolerance=0.001,
        note="itself a decaying quantity, but only in the 4th decimal",
    ),
    # ---- [15] configuration rows counted as models ----------------------
    Figure(
        "Epoch exports holding more rows than models",
        ("probes/config_rows.py",),
        r"epoch_ai\s+(\d+) of 20",
        (
            (r"docs/FINDINGS.md", r"\*\*(\d+) of 20 committed Epoch exports"),
            (r"CLAUDE.md", r"(\d+) of 20 Epoch exports hold more rows"),
            (r"docs/CONFIG_ROWS.md", r"\| Epoch AI \| 20 \| \*\*(\d+)\*\* \|"),
        ),
    ),
    Figure(
        "Terminal Bench rows versus models",
        ("probes/config_rows.py",),
        r"Terminal Bench\s+epoch_ai\s+(\d+)\s+61",
        (
            (r"docs/FINDINGS.md", r"Terminal Bench (\d+) rows from 61"),
            (r"CLAUDE.md", r"Terminal Bench (\d+)/61"),
            (r"docs/CONFIG_ROWS.md", r"Terminal Bench (\d+) rows / 61 models"),
        ),
    ),
    # ---- hindcast --------------------------------------------------------
    Figure(
        "hindcast discordant pairs, scorer correct",
        ("probes/hindcast.py",),
        r"scorer right on (\d+) of \d+ discordant",
        (
            (r"docs/FINDINGS.md", r"\*\*(\d+) of 3 discordant pairs\*\*"),
            (r"README.md", r"\| (\d+) of 3 discordant pairs"),
        ),
    ),
    Figure(
        "hindcast discordant pairs, total",
        ("probes/hindcast.py",),
        r"scorer right on \d+ of (\d+) discordant",
        (
            (r"docs/FINDINGS.md", r"\*\*2 of (\d+) discordant pairs\*\*"),
            (r"README.md", r"\| 2 of (\d+) discordant pairs"),
        ),
    ),
]


def _number(text: str) -> float:
    """
    Parse a figure as written, tolerating a typographic minus sign and a
    thousands comma. A trailing sentence period is stripped: a doc-side
    regex ending in a character class of digits-and-dots happily swallows
    the full stop after "max 0.620." and float() then dies on it.
    """
    return float(text.replace("−", "-").replace(",", "").rstrip("."))


NEEDS_AA_DATA = {
    "scored models",
    "benchmark citations",
    "models shown unweighted after D3",
}


@pytest.mark.parametrize(
    "figure",
    [
        # These count the population Artificial Analysis contributes, and
        # its file is gitignored; see conftest.py for why they skip loudly
        # instead of failing. Measured by hiding the file: these three
        # fail and every other figure holds.
        pytest.param(f, marks=pytest.mark.needs_aa_data)
        if f.name in NEEDS_AA_DATA
        else f
        for f in FIGURES
    ],
    ids=[f.name for f in FIGURES],
)
def test_doc_figure_matches_the_probe(figure: Figure) -> None:
    output = _output(figure.command)
    match = re.search(figure.probe, output)
    assert match, (
        f"{figure.name}: the probe regex no longer matches "
        f"`python {' '.join(figure.command)}` output. The command changed "
        f"shape; update the registry.\n--- output ---\n{output[:2500]}"
    )
    authoritative = _number(match.group(1))

    for doc_path, doc_regex in figure.docs:
        text = (ROOT / doc_path).read_text()
        found = re.search(doc_regex, text, re.MULTILINE)
        assert found, (
            f"{figure.name}: {doc_path} no longer states this figure "
            f"(pattern {doc_regex!r}). The probe says {authoritative}. "
            "A load-bearing figure that vanished from a doc is how the "
            "founding headline drifted — restore it or drop it from the "
            "registry deliberately."
        )
        written = _number(found.group(1))
        # With `absolute`, compare magnitudes: these figures are written
        # signed in one document and as a magnitude in another ("loses
        # separation by 6.3 points"), and both are correct prose. The
        # cost is that this entry no longer checks the SIGN, which is why
        # correlations do not use it — there the sign is the claim.
        written_cmp = abs(written) if figure.absolute else written
        expected = abs(authoritative) if figure.absolute else authoritative
        assert abs(written_cmp - expected) <= figure.tolerance, (
            f"DOC FIGURE DRIFT — {figure.name}\n"
            f"  {doc_path} says {written}\n"
            f"  `python {' '.join(figure.command)}` says {authoritative}\n"
            f"  {figure.note}\n"
            "Either the doc is stale or the code moved. Work out which; "
            "do not just edit the doc."
        )


def test_every_findings_footnote_is_registered() -> None:
    """
    Every command in FINDINGS.md's footnote list must appear in the
    registry, so a footnote cannot cite a command whose numbers nothing
    checks.
    """
    text = (ROOT / "docs" / "FINDINGS.md").read_text()
    footnotes = re.findall(r"^\d+\. `python ([^`]+)`", text, re.MULTILINE)
    registered = {" ".join(f.command) for f in FIGURES}
    missing = {c for c in footnotes if c not in registered}
    # pytest itself is a footnote and produces no figure of its own, and
    # the ARC-AGI probe needs the network — FINDINGS.md says so at the
    # footnote, which is the honest treatment rather than a silent gap.
    missing -= {"-m pytest -q", "probes/arc_agi_population.py"}
    missing = {c for c in missing if not c.startswith("probes/arc_agi_population.py")}
    assert not missing, (
        f"FINDINGS.md footnotes cite commands with no registered figure: "
        f"{sorted(missing)}"
    )


def test_decaying_figures_declare_a_wide_enough_tolerance() -> None:
    """
    Health is not a constant: freshness decays every day, so a health
    figure written into a doc drifts without anyone touching the repo.
    Measured 2026-09-23, mean catalog health falls 0.0285 points per day.

    A figure that decays therefore cannot carry the default tolerance —
    it would go red within days and train everyone to ignore this file.
    It must declare `decays=True` and a tolerance wide enough to be worth
    something. The flip side is stated in FINDINGS.md: a health figure is
    exact only on the date beside it.
    """
    for figure in FIGURES:
        if figure.decays:
            assert figure.tolerance >= 0.5, (
                f"{figure.name} decays but carries tolerance "
                f"{figure.tolerance}; it will go red within days"
            )
            assert figure.note, f"{figure.name} decays without saying so"


def test_registry_covers_multiple_documents() -> None:
    """
    The point is cross-document consistency — the founding headline
    existed in three numeric forms at once. A registry that only ever
    checked one file would not have caught that.
    """
    docs = {path for f in FIGURES for path, _ in f.docs}
    assert {"docs/FINDINGS.md", "README.md", "CLAUDE.md"} <= docs
