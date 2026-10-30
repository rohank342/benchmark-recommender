# Present so `pytest` puts the project root on sys.path and the tests can
# import the top-level modules (scoring, enrich_scores, ...) directly.
#
# It also holds the one place that decides what happens to tests which need
# data/models_raw.json.
#
# WHY. models_raw.json is gitignored (it embeds Artificial Analysis scores,
# whose free tier is internal-use only), so a fresh clone and the CI runner
# do not have it. Eleven tests read the model side of the project through it
# and, without it, fail with a message that blames the probe's regex rather
# than the missing file. They went unnoticed for five weeks because the
# commits that added them were never pushed, so CI never ran them
# (CLAUDE.md section 6).
#
# WHAT THIS DOES: tests marked `needs_hub_data` are SKIPPED when the file is
# absent, and the run says so loudly at the top and again at the bottom.
# A skip is a hole in the guarantee, not a pass, which is why it is never
# silent: the model-side doc figures are checked on a machine that has run
# `python fetch_models.py`, and NOT in CI. Do not add a mark to hide a
# failure that has some other cause.

from __future__ import annotations

from pathlib import Path

import pytest

MODELS_RAW = Path(__file__).resolve().parent / "data" / "models_raw.json"
_REASON = "data/models_raw.json is absent (gitignored) — run fetch_models.py"

_skipped: list[str] = []


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "needs_hub_data: reads data/models_raw.json; skipped, loudly, when it is absent",
    )


def pytest_report_header(config: pytest.Config) -> list[str]:
    if MODELS_RAW.exists():
        return []
    return [f"WARNING: {_REASON}. Model-side tests will be SKIPPED, not run."]


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    if MODELS_RAW.exists():
        return
    skip = pytest.mark.skip(reason=_REASON)
    for item in items:
        if "needs_hub_data" in item.keywords:
            item.add_marker(skip)
            _skipped.append(item.nodeid)


def pytest_terminal_summary(terminalreporter) -> None:
    if not _skipped:
        return
    terminalreporter.section("model-side checks NOT RUN", sep="!")
    terminalreporter.write_line(
        f"{len(_skipped)} test(s) skipped because {_REASON}."
    )
    terminalreporter.write_line(
        "These check the model-side figures quoted in the docs. A green run "
        "here does not cover them."
    )
