"""
probes/musr_baseline.py
=======================
Where MuSR's random baseline and dataset size came from.

This is the script behind `RANDOM_BASELINES["musr"]` and MuSR's
`dataset_size`. It exists because 0.33 was previously recorded on the
assumption that MuSR is a three-option benchmark, and that assumption is
wrong: one of its three subtasks is binary and another has a variable
number of options per item.

The rule in this project is that a number is either measured or marked
CURATE. This one is measured — from the dataset, not from anything
written about it. Run it to re-derive both values:

    python probes/musr_baseline.py

It hits the network (two public HF datasets) and prints its working.
Nothing else imports it; the catalog holds the committed results.
"""

from __future__ import annotations

import ast
import collections
import csv

SUBTASKS = ("murder_mystery", "object_placements", "team_allocation")


def _rows(name: str) -> list[dict]:
    from huggingface_hub import hf_hub_download

    csv.field_size_limit(10**9)
    path = hf_hub_download("TAUR-Lab/MuSR", f"{name}.csv", repo_type="dataset")
    with open(path, newline="") as handle:
        return list(csv.DictReader(handle))


def dataset_baseline() -> tuple[float, int]:
    """
    Expected accuracy of uniform random guessing, from the option counts
    of every item in the released set.
    """
    total_items = 0
    total_chance = 0.0
    print("per-subtask, counted from the released CSVs:\n")
    for name in SUBTASKS:
        rows = _rows(name)
        counts = collections.Counter(
            len(ast.literal_eval(row["choices"])) for row in rows
        )
        chance = sum(n / k for k, n in counts.items()) / len(rows)
        total_items += len(rows)
        total_chance += sum(n / k for k, n in counts.items())
        print(
            f"  {name:20} n={len(rows):4}  chance={chance:.5f}  "
            f"options={dict(sorted(counts.items()))}"
        )

    item_weighted = total_chance / total_items
    subtask_weighted = sum(
        sum(n / k for k, n in collections.Counter(
            len(ast.literal_eval(row["choices"])) for row in _rows(name)
        ).items()) / len(_rows(name))
        for name in SUBTASKS
    ) / len(SUBTASKS)

    print(f"\n  item-weighted aggregate    {item_weighted:.5f}")
    print(f"  subtask-equal-weight       {subtask_weighted:.5f}")
    print(f"  total items                {total_items}")
    print(
        "\n  The two weightings differ by 0.0007 because the subtasks are\n"
        "  near-identical in size (250/256/250), so the recorded value does\n"
        "  not depend on which aggregation the leaderboard used."
    )
    return item_weighted, total_items


def leaderboard_implied_baseline() -> None:
    """
    What baseline HF's v2 leaderboard encoded, recovered from its own
    columns. It publishes each benchmark raw and rescaled-so-chance-is-0:

        rescaled = (raw - b) / (1 - b)   =>   b = (raw - rescaled) / (1 - rescaled)

    GPQA is the control. It is a flat four-option benchmark, so if this
    inversion is right it must return exactly 0.25 for GPQA.
    """
    import pandas as pd
    from huggingface_hub import hf_hub_download

    path = hf_hub_download(
        "open-llm-leaderboard/contents",
        "data/train-00000-of-00001.parquet",
        repo_type="dataset",
    )
    frame = pd.read_parquet(path)
    columns = ["GPQA Raw", "GPQA", "BBH Raw", "BBH", "MUSR Raw", "MUSR"]
    data = frame[columns].dropna()

    print(f"\nHF Open LLM Leaderboard v2, {len(data)} models:\n")
    for name in ("GPQA", "BBH", "MUSR"):
        raw = data[f"{name} Raw"]  # 0-1
        rescaled = data[name] / 100.0  # published as a percentage
        implied = (raw - rescaled) / (1 - rescaled)
        print(
            f"  {name:5} implied baseline: median={implied.median():.5f} "
            f"std={implied.std():.5f} "
            f"p01={implied.quantile(0.01):.5f} p99={implied.quantile(0.99):.5f}"
        )


if __name__ == "__main__":
    baseline, size = dataset_baseline()
    leaderboard_implied_baseline()
    print(
        f"\nCOMMITTED: random_baseline={baseline:.3f}, dataset_size={size}.\n"
        "See fetch_benchmark_scores.RANDOM_BASELINES and MuSR's catalog entry."
    )
