# Present so `pytest` puts the project root on sys.path and the tests can
# import the top-level modules (scoring, enrich_scores, ...) directly.
#
# It also holds the one place that decides what happens to tests which need
# data/artificial_analysis.json.
#
# WHY. That file is gitignored because the Artificial Analysis free tier is
# internal-use only (README), so a fresh clone and the CI runner do not have
# it. Without it the model side loses every model that only Artificial
# Analysis scores, and the three figures counting that population cannot
# match the docs.
#
# WHAT THIS DOES: tests marked `needs_aa_data` are SKIPPED when the file is
# absent, and the run says so loudly at the top and again at the bottom.
# A skip is a hole in the guarantee, not a pass, which is why it is never
# silent: those figures are checked only on a machine that has run
# `python enrich_scores.py`, and NOT in CI. Do not add the mark to hide a
# failure that has some other cause.

from __future__ import annotations

from pathlib import Path

import pytest

AA_DATA = Path(__file__).resolve().parent / "data" / "artificial_analysis.json"
_REASON = "data/artificial_analysis.json is absent (gitignored) — run enrich_scores.py"

_skipped: list[str] = []


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "needs_aa_data: needs data/artificial_analysis.json; skipped, loudly, when absent",
    )


def pytest_report_header(config: pytest.Config) -> list[str]:
    if AA_DATA.exists():
        return []
    return [f"WARNING: {_REASON}. Tests that need it will be SKIPPED, not run."]


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    if AA_DATA.exists():
        return
    skip = pytest.mark.skip(reason=_REASON)
    for item in items:
        if "needs_aa_data" in item.keywords:
            item.add_marker(skip)
            _skipped.append(item.nodeid)


def pytest_terminal_summary(terminalreporter) -> None:
    if not _skipped:
        return
    terminalreporter.section("Artificial Analysis checks NOT RUN", sep="!")
    terminalreporter.write_line(
        f"{len(_skipped)} test(s) skipped because {_REASON}."
    )
    terminalreporter.write_line(
        "These check figures quoted in the docs. A green run here does not "
        "cover them."
    )
