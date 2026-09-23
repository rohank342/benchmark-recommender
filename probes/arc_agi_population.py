"""
probes/arc_agi_population.py
============================
How many ARC-AGI-1 models predate the window the test would need?

    python probes/arc_agi_population.py

NEEDS THE NETWORK. It lists the model directories in the HF dataset
`arcprize/arc_agi_v1_public_eval`; there is no committed copy, because
the dataset is 76 model directories of ~400 per-task JSON files each and
this repo has no reason to vendor it. That means CI cannot run this one
— it is listed in tests/test_diagnostics.py's UNCOVERABLE with that
reason, like the other fetchers.

WHY IT EXISTS. docs/ARC_AGI_TEST.md scoped ARC-AGI-1 as a candidate
independent test and recommended AGAINST building it, on the grounds
that almost all of the available models postdate the window. That figure
was quoted in docs/FINDINGS.md with no way to reproduce it, which is
exactly the thing CLAUDE.md section 9 forbids. This makes it checkable.

WHAT IT DOES NOT DO. It reads no scores and computes no outcome. It
lists directory names and dates them. The recommendation in
ARC_AGI_TEST.md stands on its own; this only re-derives the count behind
it.

DATING. The dataset carries no release-date field, but most directory
names embed a date (`o3-2025-04-16`, `claude-haiku-4-5-20251001`) and
that is used first — a date from the data rather than a guess. A short
explicit table covers the handful that do not. Anything still undated is
printed IN FULL rather than bucketed, because a name-based era is a
judgement about naming conventions and the residue is where such a
judgement would hide.

The conclusion is insensitive to that residue in the only direction that
matters: undated models can only ever ADD to the pre-window count, and
the count would have to rise from 4 to 30 to change the recommendation.
The listed names are there so a reader can check that for themselves.

RE-DERIVED 2026-09-23: 75 model directories (not 76 — one entry is the
`public_eval` data directory, not a model), of which 4 predate the
2024-06-01 as-of date. ARC_AGI_TEST.md recorded 2; both are far below
the 30-model minimum and the recommendation is unchanged.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DATASET = "arcprize/arc_agi_v1_public_eval"

# The window the test would need: a benchmark is only useful as an
# "old but unsaturated" case if enough models predate the point where
# it stopped discriminating. o3 broke ARC-AGI-1 in December 2024.
WINDOW_CLOSES = "2024-12"
AS_OF = "2024-06-01"  # the registered backtest cutoff

# MOST DIRECTORY NAMES EMBED THEIR OWN RELEASE DATE — `o3-2025-04-16`,
# `claude-haiku-4-5-20251001`. That is a date from the data, not a guess,
# so it is tried first. An earlier version of this probe skipped straight
# to family-name matching and dated `gpt-4-1-2025-04-14` (GPT-4.1, April
# 2025) to 2023 because the name starts "gpt-4-". The date was sitting in
# the string.
_EMBEDDED = (
    re.compile(r"(20\d{2})-(\d{2})-(\d{2})"),  # 2025-04-16
    re.compile(r"(20\d{2})(\d{2})(\d{2})"),  # 20251001
)

# Only for the handful with no date in the name. Short and explicit: a
# regex that guessed a month would be inventing one.
FAMILY_DATES = {
    r"^gpt-4o": "2024-05",
    r"^gpt-4$": "2023-03",
    r"^gpt-3-5": "2022-11",
    r"^claude-3-(haiku|sonnet|opus)": "2024-03",
    r"^claude-3[-.]5": "2024-06",
    r"^gemini-1": "2024-02",
    r"^qwq": "2024-11",
    r"^glm-5": "2026-01",
    r"^kimi-k2": "2025-07",
    r"^minimax-m2": "2025-10",
}

# Not a model.
SKIP = {"public_eval", "data", "README.md"}


def _dated(name: str) -> str | None:
    """Month this model became available, or None if it cannot be dated."""
    for pattern in _EMBEDDED:
        found = pattern.search(name)
        if found:
            return f"{found.group(1)}-{found.group(2)}"
    lowered = name.lower()
    for pattern, month in FAMILY_DATES.items():
        if re.search(pattern, lowered):
            return month
    return None


def main() -> None:
    try:
        from huggingface_hub import list_repo_files
    except ImportError:
        print("huggingface_hub is not installed; cannot list the dataset.")
        return

    print(f"\nARC-AGI-1 POPULATION — {DATASET}\n")
    try:
        files = list_repo_files(DATASET, repo_type="dataset")
    except Exception as error:  # network, auth, rename, deletion
        print(f"  could not list the dataset: {type(error).__name__}: {error}")
        print(
            "\n  This probe needs the network. The figure it re-derives is\n"
            "  quoted in docs/FINDINGS.md as a record of a past run, dated\n"
            "  and attributed, precisely because it cannot be checked offline."
        )
        return

    # Model directories are the first path segment under the data root.
    directories = sorted({f.split("/")[0] for f in files if "/" in f})
    directories = [
        d for d in directories if not d.startswith(".") and d not in SKIP
    ]
    print(f"  model directories: {len(directories)}\n")

    before, within, after, undated = [], [], [], []
    for name in directories:
        month = _dated(name)
        if month is None:
            undated.append(name)
        elif month < AS_OF[:7]:
            before.append((name, month))
        elif month <= WINDOW_CLOSES:
            within.append((name, month))
        else:
            after.append((name, month))

    print(f"  predating the {AS_OF} as-of date        {len(before)}")
    for name, month in sorted(before, key=lambda x: x[1]):
        print(f"      {month}  {name}")
    print(f"  between that and the window's close    {len(within)}")
    print(f"  after {WINDOW_CLOSES}, when o3 broke it{'':<10}{len(after)}")
    print(f"  not datable from the name              {len(undated)}")
    print("      (listed in full: they can only ADD to the pre-window count,")
    print("       which would have to reach 30 to change the recommendation)")
    for name in undated:
        print(f"      ?        {name}")

    print(
        f"\n  The saturation minimum is 30 models. At {AS_OF} this dataset\n"
        f"  offers {len(before)}. ARC-AGI-1 at a 2024 as-of date would therefore be\n"
        "  THIN tier — discrimination unmeasurable, score resting on\n"
        "  freshness alone — and a thin-tier benchmark cannot be compared\n"
        "  with the partial-tier comparators at all. That is precisely how\n"
        "  Candidate 1 died. See docs/ARC_AGI_TEST.md, which recommends\n"
        "  against building this and is not superseded by this probe."
    )


if __name__ == "__main__":
    main()
