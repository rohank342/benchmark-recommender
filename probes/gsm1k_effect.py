"""
probes/gsm1k_effect.py
======================
Where GSM8K's `contamination_effect` of 0.051 came from.

The catalog carried a CURATE marker for months saying the published
"accuracy drops of up to 8%" is a MAXIMUM across models, while every other
contamination_effect in this project is a MEAN across a model set, and that
the fix was to extract a mean from the paper's own per-model results.

This does that, from the paper rather than from anything written about it:

    python probes/gsm1k_effect.py

It downloads arXiv 2405.00332 (v4, the NeurIPS 2024 D&B version), parses
the full results table in Appendix F, and prints its working.

VALIDATION: the maximum absolute drop this parse finds must equal 8.0
points, the paper's headline figure. If it does not, the parse is wrong and
the mean is worthless — the script asserts it.

Requires pypdf. Nothing else imports this; the catalog holds the result.
"""

from __future__ import annotations

import re
import statistics
import subprocess
import sys
import tempfile
from pathlib import Path

PDF_URL = "https://arxiv.org/pdf/2405.00332v4"
ROW = re.compile(
    r"^(.+?)\s*(-?\d\.\d{3})\s+(\d\.\d{3})\s+(\d\.\d{3})\s+(-?\d+\.\d+)\s+(\d\.\d+)\s*$"
)


def _text() -> str:
    import pypdf

    path = Path(tempfile.gettempdir()) / "gsm1k_v4.pdf"
    if not path.exists():
        subprocess.run(
            ["curl", "-sL", "--max-time", "120", PDF_URL, "-o", str(path)], check=True
        )
    reader = pypdf.PdfReader(str(path))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def standard_prompt_rows(text: str) -> list[dict]:
    """
    Appendix F's table, standard-prompt half only.

    The paper reports two prompt formats. The standard LM-Eval-Harness
    prompt is the one its headline numbers use, so that is the one taken;
    the alternative-prompt half is reported separately below as a check
    rather than pooled, because pooling would double-count every model.
    """
    lines = text.split("\n")
    start = next(i for i, line in enumerate(lines) if line.strip() == "F Results Table")
    end = next(
        i for i, line in enumerate(lines) if line.strip() == "Alternative Prompt" and i > start
    )

    rows = []
    for line in lines[start:end]:
        line = line.strip()
        if not line or line.startswith("Model Diff") or line == "Standard Prompt":
            continue
        match = ROW.match(line)
        if not match:
            continue
        name, diff, gsm8k, gsm1k = (
            match.group(1).strip(),
            float(match.group(2)),
            float(match.group(3)),
            float(match.group(4)),
        )
        # The table's own Diff column is the check on the row parse.
        if abs((gsm8k - gsm1k) - diff) > 0.0015:
            raise ValueError(f"row does not self-check: {line}")
        rows.append({"model": name, "gsm8k": gsm8k, "gsm1k": gsm1k})
    return rows


def main() -> None:
    rows = standard_prompt_rows(_text())
    for row in rows:
        row["relative"] = (row["gsm8k"] - row["gsm1k"]) / row["gsm8k"]

    absolute = [r["gsm8k"] - r["gsm1k"] for r in rows]
    relative = [r["relative"] for r in rows]

    print(f"models parsed: {len(rows)}\n")
    print(f"  max ABSOLUTE drop  {max(absolute) * 100:.1f} points  <- paper's headline")
    assert abs(max(absolute) - 0.080) < 0.0005, "parse failed its validation check"
    print(f"  mean ABSOLUTE drop {statistics.mean(absolute) * 100:.1f} points")
    print()
    print(f"  MEAN RELATIVE drop {statistics.mean(relative):.4f}  <- contamination_effect")
    print(f"  median relative    {statistics.median(relative):.4f}")

    floored = [r for r in rows if r["gsm8k"] >= 0.10]
    print(
        f"\n  excluding the {len(rows) - len(floored)} models under 10% on GSM8K "
        f"(tiny denominators inflate a ratio): {statistics.mean([r['relative'] for r in floored]):.4f}"
    )
    print(
        "  No filter is applied to the committed value: any threshold would be\n"
        "  a choice nobody can source, and it moves the answer by 0.007."
    )

    worst = sorted(rows, key=lambda r: -r["relative"])[:3]
    best = sorted(rows, key=lambda r: r["relative"])[:3]
    print("\n  most overfit:")
    for r in worst:
        print(f"    {r['model']:32} {r['gsm8k']:.3f} -> {r['gsm1k']:.3f}  {r['relative']:+.3f}")
    print("  best generalizing (negative = scored HIGHER on the fresh set):")
    for r in best:
        print(f"    {r['model']:32} {r['gsm8k']:.3f} -> {r['gsm1k']:.3f}  {r['relative']:+.3f}")

    print(f"\nCOMMITTED: contamination_effect={statistics.mean(relative):.3f}")
    print("See fetch_benchmarks.py, GSM8K entry, for why this is only partly")
    print("comparable to HumanEval's 0.394.")


if __name__ == "__main__":
    sys.exit(main())
