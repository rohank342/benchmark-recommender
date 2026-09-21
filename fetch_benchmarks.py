"""
fetch_benchmarks.py
===================
The catalog of benchmarks this project reasons about.

The premise of the project: a benchmark's popularity says nothing about
whether it still discriminates between models. Labs optimize against
well-known benchmarks until the top of the leaderboard is a cluster of
near-identical numbers, and old test sets leak into training corpora. So
benchmarks need to be assessed before model scores mean anything.

Two kinds of data live here:

  MEASURED — pulled from Epoch AI's export in data/epoch_benchmarks/.
  Per-model scores let saturation be computed rather than asserted, and
  the metadata file supplies each benchmark's score column, scale and
  ceiling. benchmark_scoring.py does that computation.

  CURATED — release dates, dataset sizes, contamination/saturation
  flags, evaluator counts, task specificity. These come from reading
  papers and reports, not from an API. Every one is marked CURATE(you)
  with what to look for, and `curation_notes` records the current basis
  so a guess is never mistaken for a finding.

Nothing here hits the network: the Epoch export is a local download and
the catalog is source code. Editing the catalog is the intended way to
add a benchmark.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

DATA_DIR = Path(__file__).parent / "data"
EPOCH_DIR = DATA_DIR / "epoch_benchmarks"
EPOCH_METADATA_FILE = "benchmark_metadata.csv"

# Task categories. task_matcher.py maps free-text task descriptions onto
# these, so adding a category means teaching the matcher its vocabulary.
CATEGORIES = (
    "code generation",
    "software engineering",
    "agentic tool use",
    "general knowledge",
    "scientific reasoning",
    "mathematical reasoning",
    "commonsense reasoning",
    "factual accuracy",
    "computer use",
)


@dataclass
class Benchmark:
    """One benchmark, with everything known about its trustworthiness."""

    key: str
    name: str
    category: str
    # Names other sources use for the same benchmark, so model scores can
    # be attributed back to it (see scoring.py).
    aliases: tuple[str, ...] = ()

    # --- CURATED FIELDS ------------------------------------------------
    release_date: Optional[str] = None  # ISO date the test set went public
    dataset_size: Optional[int] = None  # number of items/questions
    # Publicly reported contamination or train/test leakage.
    contamination_flagged: bool = False
    # Publicly discussed as saturated. Note this is the *reported* status;
    # benchmark_scoring.py also measures saturation where data allows, and
    # the two disagreeing is itself informative.
    saturation_flagged: bool = False
    # Independent evaluators/leaderboards publishing scores on it.
    independent_evaluators: int = 1
    # 0-1: how narrowly this maps to one real task. 1.0 = measures one
    # concrete skill (resolving GitHub issues); 0.2 = broad catch-all.
    task_specificity: float = 0.5
    curation_notes: str = ""

    # --- MEASURED ------------------------------------------------------
    # Filename inside data/epoch_benchmarks/ holding per-model scores.
    epoch_source_file: Optional[str] = None

    def matches(self, label: Optional[str]) -> bool:
        """Does an external source's benchmark label refer to this one?"""
        if not label:
            return False
        normalized = _normalize(label)
        return normalized in {_normalize(self.name), self.key} | {
            _normalize(alias) for alias in self.aliases
        }


def _normalize(label: str) -> str:
    return "".join(ch for ch in label.lower() if ch.isalnum())


########################################################################
# CURATE(you): THE BENCHMARK CATALOG
#
# Every field below the `category` line is a research judgement, not an
# API result. The values here are starting positions drawn from what is
# widely reported; replace them with what you find and update
# `curation_notes` as you go. The fields that most change the output:
#
#   contamination_flagged — HF's ASR overfitting study, Epoch AI's
#       contamination notes, the LMSYS/LiveBench leakage discussions.
#   saturation_flagged    — where the literature says the benchmark has
#       stopped discriminating. Compare against the *measured*
#       saturation benchmark_scoring.py computes; disagreement is a
#       signal worth chasing.
#   independent_evaluators — count leaderboards/orgs publishing scores
#       (HF Open LLM Leaderboard, Epoch, Artificial Analysis, LMArena,
#       Papers-with-Code, the original authors).
#   task_specificity      — your judgement of how narrowly it maps to a
#       real task.
########################################################################

BENCHMARK_CATALOG: tuple[Benchmark, ...] = (
    Benchmark(
        key="mmlu",
        name="MMLU",
        category="general knowledge",
        aliases=("Massive Multitask Language Understanding", "mmlu_external"),
        release_date="2020-09-07",
        dataset_size=15908,
        contamination_flagged=True,
        saturation_flagged=True,
        independent_evaluators=6,
        task_specificity=0.2,
        curation_notes=(
            "CURATE(you): widely reported as both contaminated and saturated — "
            "verify against HF's ASR overfitting study and Epoch's notes. Its "
            "breadth is the point, so specificity is deliberately low."
        ),
        epoch_source_file="mmlu_external.csv",
    ),
    Benchmark(
        key="mmlu_pro",
        name="MMLU-Pro",
        category="general knowledge",
        aliases=("MMLU Pro",),
        release_date="2024-06-03",
        dataset_size=12032,
        contamination_flagged=False,
        saturation_flagged=False,
        independent_evaluators=3,
        task_specificity=0.25,
        curation_notes=(
            "CURATE(you): built explicitly to de-saturate MMLU (harder distractors, "
            "10 options). No Epoch score file in the export, so saturation cannot "
            "be measured here — find a leaderboard export or mark it unknown."
        ),
        epoch_source_file=None,
    ),
    Benchmark(
        key="gpqa_diamond",
        name="GPQA Diamond",
        category="scientific reasoning",
        aliases=("GPQA", "GPQA-Diamond", "gpqa diamond", "gpqa_diamond"),
        release_date="2023-11-20",
        dataset_size=198,
        contamination_flagged=False,
        saturation_flagged=False,
        independent_evaluators=5,
        task_specificity=0.6,
        curation_notes=(
            "CURATE(you): 'Google-proof' by construction, written by domain PhDs. "
            "Diamond subset is only 198 questions, so single-run scores are noisy — "
            "worth reflecting in reproducibility once you have multi-run data."
        ),
        epoch_source_file="gpqa_diamond.csv",
    ),
    Benchmark(
        key="humaneval",
        name="HumanEval",
        category="code generation",
        aliases=("HumanEval+", "openai_humaneval", "human eval", "pass@1"),
        release_date="2021-07-07",
        dataset_size=164,
        contamination_flagged=True,
        saturation_flagged=True,
        independent_evaluators=6,
        task_specificity=0.45,
        curation_notes=(
            "CURATE(you): the canonical example of the problem this project exists "
            "for — 164 short functions, published 2021, top models cluster above 90%. "
            "No Epoch file, so saturation is asserted rather than measured; a "
            "leaderboard export would let us prove it."
        ),
        epoch_source_file=None,
    ),
    Benchmark(
        key="livecodebench",
        name="LiveCodeBench",
        category="code generation",
        aliases=("Live Code Bench",),
        release_date="2024-03-12",
        dataset_size=400,
        contamination_flagged=False,
        saturation_flagged=False,
        independent_evaluators=3,
        task_specificity=0.7,
        curation_notes=(
            "CURATE(you): continuously refreshed from recent contest problems, which "
            "is a structural defence against leakage — verify how the release windows "
            "are handled before trusting cross-version comparisons."
        ),
        epoch_source_file=None,
    ),
    Benchmark(
        key="swe_bench_verified",
        name="SWE-Bench Verified",
        category="software engineering",
        aliases=("SWE-bench", "SWE-Bench verified", "SWE-bench Verified", "swebench"),
        release_date="2024-08-13",
        dataset_size=500,
        contamination_flagged=False,
        saturation_flagged=False,
        independent_evaluators=5,
        task_specificity=0.95,
        curation_notes=(
            "CURATE(you): human-validated subset of real GitHub issues — about as "
            "close to a real task as this catalog gets. Watch for repo-level leakage "
            "as the underlying projects are public."
        ),
        epoch_source_file="swe_bench_verified.csv",
    ),
    Benchmark(
        key="hellaswag",
        name="HellaSwag",
        category="commonsense reasoning",
        aliases=("hella swag", "hella_swag_external"),
        release_date="2019-05-19",
        dataset_size=10042,
        contamination_flagged=True,
        saturation_flagged=True,
        independent_evaluators=5,
        task_specificity=0.2,
        curation_notes=(
            "CURATE(you): 2019 vintage, long since in every crawl. Included mainly "
            "as a reference point for what a fully saturated benchmark looks like."
        ),
        epoch_source_file="hella_swag_external.csv",
    ),
    Benchmark(
        key="bbh",
        name="BIG-Bench Hard",
        category="commonsense reasoning",
        aliases=("BBH", "BIG-Bench-Hard", "bbh_external"),
        release_date="2022-10-17",
        dataset_size=6511,
        contamination_flagged=True,
        saturation_flagged=True,
        independent_evaluators=4,
        task_specificity=0.3,
        curation_notes=(
            "CURATE(you): the 23 tasks BIG-Bench models struggled with in 2022; "
            "several are now largely solved. Per-task saturation varies a lot, so a "
            "single aggregate hides the picture."
        ),
        epoch_source_file="bbh_external.csv",
    ),
    Benchmark(
        key="truthfulqa",
        name="TruthfulQA",
        category="factual accuracy",
        aliases=("Truthful QA",),
        release_date="2021-09-08",
        dataset_size=817,
        contamination_flagged=True,
        saturation_flagged=False,
        independent_evaluators=4,
        task_specificity=0.4,
        curation_notes=(
            "CURATE(you): not in the Epoch export, so no measured saturation. Also "
            "measures imitation of human misconceptions rather than factual accuracy "
            "as such — consider whether the category label above is right."
        ),
        epoch_source_file=None,
    ),
    Benchmark(
        key="arc",
        name="ARC (AI2 Reasoning Challenge)",
        category="scientific reasoning",
        aliases=("ARC", "ARC-Challenge", "ARC AI2", "arc_ai2_external", "ai2_arc"),
        release_date="2018-03-14",
        dataset_size=7787,
        contamination_flagged=True,
        saturation_flagged=True,
        independent_evaluators=5,
        task_specificity=0.25,
        curation_notes=(
            "CURATE(you): 2018 grade-school science questions. Like HellaSwag, kept "
            "as a calibration point for the saturated end of the scale."
        ),
        epoch_source_file="arc_ai2_external.csv",
    ),
    # --- Benchmarks that arrived with the Epoch export ------------------
    # These weren't in the original brief but come with real per-model
    # scores, so their saturation is measured rather than asserted.
    Benchmark(
        key="mirrorcode",
        name="MirrorCode",
        category="code generation",
        aliases=("Mirror Code",),
        release_date="2026-06-26",
        contamination_flagged=False,
        saturation_flagged=False,
        independent_evaluators=2,
        task_specificity=0.8,
        curation_notes="CURATE(you): recent Epoch-run benchmark; confirm construction and refresh policy.",
        epoch_source_file="mirrorcode.csv",
    ),
    Benchmark(
        key="aider_polyglot",
        name="Aider polyglot",
        category="code generation",
        aliases=("Aider Polyglot", "aider",),
        release_date="2024-12-21",
        dataset_size=225,
        contamination_flagged=False,
        saturation_flagged=False,
        independent_evaluators=3,
        task_specificity=0.85,
        curation_notes="CURATE(you): edit-format-sensitive; measures applying diffs, not just writing code.",
        epoch_source_file="aider_polyglot_external.csv",
    ),
    Benchmark(
        key="terminal_bench",
        name="Terminal Bench",
        category="agentic tool use",
        aliases=("TerminalBench", "terminalbench", "terminalbench_hard"),
        release_date="2025-05-01",
        contamination_flagged=False,
        saturation_flagged=False,
        independent_evaluators=3,
        task_specificity=0.9,
        curation_notes="CURATE(you): verify release date and harness version — scores move between harnesses.",
        epoch_source_file="terminalbench_external.csv",
    ),
    Benchmark(
        key="gso_bench",
        name="GSO-Bench",
        category="software engineering",
        aliases=("GSO", "gso_external"),
        release_date="2025-07-01",
        contamination_flagged=False,
        saturation_flagged=False,
        independent_evaluators=2,
        task_specificity=0.85,
        curation_notes="CURATE(you): confirm release date and what the OPT@1 scorer rewards.",
        epoch_source_file="gso_external.csv",
    ),
    Benchmark(
        key="deepswe",
        name="DeepSWE",
        category="software engineering",
        aliases=("Deep SWE",),
        release_date="2026-05-26",
        contamination_flagged=False,
        saturation_flagged=False,
        independent_evaluators=2,
        task_specificity=0.9,
        curation_notes="CURATE(you): recent; little independent reporting yet.",
        epoch_source_file="deepswe_external.csv",
    ),
    Benchmark(
        key="frontiercode",
        name="FrontierCode",
        category="code generation",
        aliases=("Frontier Code",),
        release_date="2026-06-08",
        contamination_flagged=False,
        saturation_flagged=False,
        independent_evaluators=2,
        task_specificity=0.8,
        curation_notes="CURATE(you): recent; little independent reporting yet.",
        epoch_source_file="frontiercode_external.csv",
    ),
    Benchmark(
        key="math_level_5",
        name="MATH Level 5",
        category="mathematical reasoning",
        aliases=("MATH", "hendrycks_math", "MATH lvl 5"),
        release_date="2021-03-05",
        dataset_size=1324,
        contamination_flagged=True,
        saturation_flagged=True,
        independent_evaluators=5,
        task_specificity=0.5,
        curation_notes=(
            "CURATE(you): Epoch explicitly warns about contamination here — many "
            "models are fine-tuned on mathematical content overlapping the test set."
        ),
        epoch_source_file="math_level_5.csv",
    ),
    Benchmark(
        key="hle",
        name="Humanity's Last Exam",
        category="scientific reasoning",
        aliases=("HLE", "hle_external"),
        release_date="2025-01-23",
        dataset_size=2500,
        contamination_flagged=False,
        saturation_flagged=False,
        independent_evaluators=4,
        task_specificity=0.35,
        curation_notes="CURATE(you): built to be hard for frontier models; watch for rapid saturation.",
        epoch_source_file="hle_external.csv",
    ),
    Benchmark(
        key="simpleqa_verified",
        name="SimpleQA Verified",
        category="factual accuracy",
        aliases=("SimpleQA", "simpleqa_verified"),
        release_date="2024-10-30",
        dataset_size=1000,
        contamination_flagged=False,
        saturation_flagged=False,
        independent_evaluators=3,
        task_specificity=0.7,
        curation_notes="CURATE(you): short-form factuality; confirm the verified subset's provenance.",
        epoch_source_file="simpleqa_verified.csv",
    ),
    Benchmark(
        key="osworld",
        name="OSWorld",
        category="computer use",
        aliases=("OS World", "os_world_external"),
        release_date="2024-04-11",
        dataset_size=369,
        contamination_flagged=False,
        saturation_flagged=False,
        independent_evaluators=3,
        task_specificity=0.9,
        curation_notes="CURATE(you): real desktop environments; scores depend heavily on the agent scaffold.",
        epoch_source_file="os_world_external.csv",
    ),
    Benchmark(
        key="the_agent_company",
        name="The Agent Company",
        category="agentic tool use",
        aliases=("TheAgentCompany", "the_agent_company_external"),
        release_date="2024-12-18",
        contamination_flagged=False,
        saturation_flagged=False,
        independent_evaluators=2,
        task_specificity=0.9,
        curation_notes="CURATE(you): simulated workplace tasks; confirm dataset size and scoring.",
        epoch_source_file="the_agent_company_external.csv",
    ),
    Benchmark(
        key="triviaqa",
        name="TriviaQA",
        category="general knowledge",
        aliases=("Trivia QA", "trivia_qa_external"),
        release_date="2017-05-09",
        dataset_size=95000,
        contamination_flagged=True,
        saturation_flagged=True,
        independent_evaluators=4,
        task_specificity=0.3,
        curation_notes="CURATE(you): 2017 web-sourced trivia; assume full contamination.",
        epoch_source_file="trivia_qa_external.csv",
    ),
)


@dataclass
class BenchmarkScores:
    """Per-model scores for one benchmark, normalized to 0-1."""

    benchmark_key: str
    scores: list[float] = field(default_factory=list)
    model_names: list[str] = field(default_factory=list)
    ceiling: float = 1.0
    random_baseline: float = 0.0
    source: str = "epoch_ai"


def _epoch_metadata(path: Path = EPOCH_DIR) -> dict[str, dict[str, str]]:
    """Epoch's index: score column, scale factor, ceiling, per benchmark file."""
    metadata_path = path / EPOCH_METADATA_FILE
    if not metadata_path.exists():
        return {}
    with metadata_path.open(newline="", encoding="utf-8") as handle:
        return {
            (row.get("source_file") or "").strip(): row
            for row in csv.DictReader(handle)
            if (row.get("source_file") or "").strip()
        }


def load_benchmark_scores(
    benchmark: Benchmark, path: Path = EPOCH_DIR
) -> Optional[BenchmarkScores]:
    """
    Every model score recorded for this benchmark, normalized to 0-1.

    Returns None when the benchmark has no local score file — which is
    not a failure, just the boundary between measured and curated. The
    caller is expected to say which it is rather than paper over it.
    """
    if not benchmark.epoch_source_file:
        return None
    metadata = _epoch_metadata(path).get(benchmark.epoch_source_file)
    file_path = path / benchmark.epoch_source_file
    if not metadata or not file_path.exists():
        return None

    score_column = (metadata.get("score_column") or "").strip()
    try:
        scale = float(metadata.get("scale") or 1.0)
    except ValueError:
        scale = 1.0
    try:
        ceiling = float(metadata.get("score_ceiling") or 1.0)
    except ValueError:
        ceiling = 1.0
    try:
        baseline = float(metadata.get("random_baseline") or 0.0)
    except ValueError:
        baseline = 0.0

    scores: list[float] = []
    names: list[str] = []
    with file_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        model_column = next(
            (c for c in (reader.fieldnames or []) if c.strip().lower() in
             ("model version", "model", "model name")),
            None,
        )
        if score_column not in (reader.fieldnames or []):
            return None
        for row in reader:
            raw = (row.get(score_column) or "").strip().rstrip("%")
            if not raw:
                continue
            try:
                scores.append(float(raw) * scale)
            except ValueError:
                continue
            names.append((row.get(model_column) or "").strip() if model_column else "")

    if not scores:
        return None
    return BenchmarkScores(
        benchmark_key=benchmark.key,
        scores=scores,
        model_names=names,
        ceiling=ceiling,
        random_baseline=baseline,
    )


def load_benchmark_catalog() -> tuple[Benchmark, ...]:
    """The catalog. A function so callers don't depend on module state."""
    return BENCHMARK_CATALOG


def benchmarks_by_category(category: str) -> list[Benchmark]:
    return [b for b in BENCHMARK_CATALOG if b.category == category]


def find_benchmark(label: Optional[str]) -> Optional[Benchmark]:
    """Resolve an external source's benchmark label to a catalog entry."""
    for benchmark in BENCHMARK_CATALOG:
        if benchmark.matches(label):
            return benchmark
    return None


if __name__ == "__main__":
    catalog = load_benchmark_catalog()
    measured = [b for b in catalog if b.epoch_source_file]
    print(f"{len(catalog)} benchmarks, {len(measured)} with local score data\n")
    for benchmark in catalog:
        scores = load_benchmark_scores(benchmark)
        basis = f"{len(scores.scores)} model scores" if scores else "curated only"
        print(f"  {benchmark.name:<32} {benchmark.category:<24} {basis}")
