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
# Score sets pulled by fetch_benchmark_scores.py, named
# "<benchmark key>__<source>.csv" with columns model,score (0-1).
SCORES_DIR = DATA_DIR / "benchmark_scores"

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
    # Fraction of items found in a major pretraining corpus, where a study
    # has quantified it (MMLU 0.277 and MMLU-Pro 0.162 against
    # DCLM-baseline). The flag alone can't distinguish 16% from 28%, and
    # that difference matters, so the rate scales the penalty when known.
    contamination_rate: Optional[float] = None
    # Observed relative score inflation: how far scores fall when the same
    # models are re-evaluated on a decontaminated variant (HumanEval:
    # 0.394 across 51 LLMs). This is the *effect* rather than the rate,
    # and the two can diverge sharply — HumanEval's overlap rate is modest
    # but its inflation is severe, because 164 short functions leave
    # little room for partial memorization to not help.
    contamination_effect: Optional[float] = None
    # Publicly discussed as saturated. Note this is the *reported* status;
    # benchmark_scoring.py also measures saturation where data allows, and
    # the two disagreeing is itself informative.
    saturation_flagged: bool = False
    # Independent evaluators/leaderboards publishing scores on it.
    independent_evaluators: int = 1
    # 0-1: how narrowly this maps to one real task. 1.0 = measures one
    # concrete skill (resolving GitHub issues); 0.2 = broad catch-all.
    task_specificity: float = 0.5
    # How the test set resists leaking into training data:
    #   "public_static"  — published once, public ever since. Decays with age.
    #   "refreshed"      — new items added on a rolling basis (LiveCodeBench's
    #                      release windows, Epoch's re-runs), so the effective
    #                      age of what's being scored stays low.
    #   "private_holdout" — answers withheld; scoring runs server-side.
    # HF's Open ASR Leaderboard study is the argument for tracking this:
    # the models with the best scores were the most likely to reproduce
    # benchmark-specific reference errors, and their recommended fix was
    # "fully held-out evaluation sets" with temporal separation.
    # https://huggingface.co/blog/asr-benchmark-optimization
    holdout: str = "public_static"
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
        contamination_rate=0.277,
        saturation_flagged=True,
        independent_evaluators=6,
        task_specificity=0.2,
        curation_notes=(
            "RESEARCHED 2026-09-20. Contamination: 27.7% of MMLU items appear in "
            "DCLM-baseline. Quality: Gema et al., 'Are We Done with MMLU?' "
            "(NAACL 2025) hand-checked 5,700 questions and found a 6.49% label "
            "error rate — 57% in the Virology subset — and showed that fixing "
            "labels changes model rankings, so the noise is not symmetric. "
            "Saturation: retired from HF's Open LLM Leaderboard in June 2024 "
            "along with ARC/HellaSwag/TruthfulQA/Winogrande/GSM8K because the "
            "set had saturated. https://aclanthology.org/2025.naacl-long.262/ | "
            "https://huggingface.co/docs/leaderboards/en/open_llm_leaderboard/archive"
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
        contamination_flagged=True,
        contamination_rate=0.162,
        saturation_flagged=False,
        independent_evaluators=3,
        task_specificity=0.25,
        curation_notes=(
            "RESEARCHED 2026-09-20. Built to de-saturate MMLU (10 options, harder "
            "distractors) and picked for HF's Open LLM Leaderboard v2 in June 2024. "
            "Contamination: 16.2% dirty against DCLM-baseline — better than MMLU's "
            "27.7%, not clean. Saturation: reported frontier clustering within ~5 "
            "points (83-90%), which is tighter than GPQA Diamond's 15-point spread; "
            "CURATE(you) — that is a secondhand figure, and with no Epoch score file "
            "it can't be measured here. Finding a leaderboard export is the fix."
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
        saturation_flagged=True,
        independent_evaluators=5,
        task_specificity=0.6,
        curation_notes=(
            "RESEARCHED 2026-09-20. Saturation flag added on evidence, and it "
            "matches what this repo measures independently (~89% from Epoch's "
            "score distribution). Frontier scores compressed from below the "
            "non-expert baseline to clustered above 94% between Nov 2023 and Apr "
            "2026; as of Sep 2026 the top four span 0.5 points — roughly ONE "
            "question on a 198-item test, i.e. statistically indistinguishable. "
            "Still 'Google-proof' by construction and written by domain PhDs, so "
            "the questions are sound; it has simply been answered. "
            "CURATE(you): the 198-item size also makes single runs noisy — worth "
            "reflecting in reproducibility once multi-run data exists."
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
        contamination_rate=0.13,  # midpoint of the reported 8-18% range
        contamination_effect=0.394,  # mean score drop across 51 LLMs when decontaminated
        saturation_flagged=True,
        independent_evaluators=6,
        task_specificity=0.45,
        curation_notes=(
            "RESEARCHED 2026-09-20. The canonical case for this project. "
            "Contamination is quantified, not just suspected: 8-18% of items appear "
            "in major open-weight pretraining corpora, and across 51 LLMs scores "
            "fall by an average of 39.4% when the same models are evaluated on "
            "decontaminated variants. 164 short functions, public since 2021. "
            "https://arxiv.org/pdf/2403.04811 | https://arxiv.org/pdf/2412.01526 "
            "CURATE(you): saturation is still ASSERTED here, not measured — no "
            "Epoch score file. An EvalPlus export would let the 39.4% figure be "
            "reproduced in-repo rather than cited."
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
        holdout="refreshed",
        curation_notes=(
            "RESEARCHED 2026-09-20. Marked `refreshed`: problems are drawn "
            "continuously from recent contests and scored in release windows, so "
            "models are largely tested on material published after their training "
            "cutoff. This is the structural defence HF's ASR study argues for, and "
            "it is why age alone understates this benchmark. "
            "CURATE(you): verify the current window policy before comparing scores "
            "across versions — a cross-window comparison is not like-for-like."
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
            "RESEARCHED 2026-09-20. Human-validated subset of 500 real GitHub "
            "issues — the closest thing in this catalog to a real task, hence the "
            "0.95 specificity. Measured saturation here is already ~70%, so it is "
            "trending the way the others did. "
            "CURATE(you): the underlying repositories are public, so both the issues "
            "and their accepted patches are crawlable. No contamination flag yet "
            "because I found no study quantifying it — that absence is the thing to "
            "check, not evidence of cleanliness."
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
            "RESEARCHED 2026-09-20. Retired from HF's Open LLM Leaderboard in June "
            "2024, explicitly because the v1 set had saturated — models scored high "
            "enough that it stopped separating them. 2019 vintage, so assume it is "
            "in every crawl. Kept here as the calibration point for 'do not trust'. "
            "https://huggingface.co/docs/leaderboards/en/open_llm_leaderboard/archive"
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
            "RESEARCHED 2026-09-20. Worth noting the trajectory: BBH was one of the "
            "HARDER benchmarks chosen for HF's Open LLM Leaderboard v2 in June 2024, "
            "as a replacement for the saturated v1 set — and this repo now measures "
            "it at ~48% saturation. A replacement benchmark aging into the same "
            "condition in two years is the pattern this project exists to surface. "
            "CURATE(you): it aggregates 23 tasks with very different saturation "
            "levels, so one number hides the picture — per-task scoring would be "
            "more honest."
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
            "RESEARCHED 2026-09-20. Retired from HF's Open LLM Leaderboard in June "
            "2024 with the rest of the v1 set. Note it measures imitation of common "
            "human misconceptions, not factual accuracy in general — the category "
            "label here is a stretch. "
            "CURATE(you): no Epoch score file, so saturation is unmeasured; and "
            "decide whether this belongs under 'factual accuracy' at all."
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
            "RESEARCHED 2026-09-20. 2018 grade-school science questions; retired "
            "from HF's Open LLM Leaderboard alongside HellaSwag/MMLU/TruthfulQA in "
            "June 2024 for saturation. Calibration point for the saturated end. "
            "https://huggingface.co/docs/leaderboards/en/open_llm_leaderboard/archive"
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
            "RESEARCHED 2026-09-20. Epoch explicitly warns about contamination: many "
            "models are fine-tuned on mathematical content that overlaps the test "
            "set, so scores flatter. Also chosen for HF's Open LLM Leaderboard v2 in "
            "June 2024 as a harder replacement, and this repo now measures it at 94% "
            "saturation — the most saturated benchmark in the catalog. "
            "https://epoch.ai/benchmarks"
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


def load_external_score_sets(
    benchmark: Benchmark, path: Path = SCORES_DIR
) -> list[BenchmarkScores]:
    """
    Score sets pulled from leaderboards by fetch_benchmark_scores.py.

    A benchmark can have several — the same benchmark measured by
    different evaluators — which is what makes cross-source agreement
    checkable rather than assumed.
    """
    if not path.exists():
        return []
    sets: list[BenchmarkScores] = []
    for file_path in sorted(path.glob(f"{benchmark.key}__*.csv")):
        source = file_path.stem.split("__", 1)[1]
        scores: list[float] = []
        names: list[str] = []
        with file_path.open(newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                try:
                    scores.append(float(row["score"]))
                except (KeyError, TypeError, ValueError):
                    continue
                names.append((row.get("model") or "").strip())
        if scores:
            sets.append(
                BenchmarkScores(
                    benchmark_key=benchmark.key,
                    scores=scores,
                    model_names=names,
                    ceiling=1.0,
                    random_baseline=0.0,
                    source=source,
                )
            )
    return sets


def load_score_sets(benchmark: Benchmark) -> list[BenchmarkScores]:
    """Every score distribution available for this benchmark, any source."""
    sets = load_external_score_sets(benchmark)
    epoch = load_epoch_scores(benchmark)
    if epoch is not None:
        sets.insert(0, epoch)
    return sets


# What population each score source covers. This decides what a
# saturation reading *means*, and the sources disagree sharply: on GPQA
# Diamond the frontier's top 10 sit at 93% of the usable range while the
# open-community leaderboard's top 10 sit at 27%. Both are true; they
# answer different questions.
SOURCE_POPULATIONS = {
    "epoch_ai": "frontier models",
    "open_llm_leaderboard_v2": "open community models (HF leaderboard v2)",
    "open_llm_leaderboard_v1": "open community models (HF leaderboard v1)",
    "evalplus": "code models submitted to EvalPlus",
}

# Preference order for the headline reading. Frontier coverage wins over
# sample size: "has this benchmark stopped separating the best models?"
# is the question people are actually asking when they pick a benchmark,
# and a thousand weak models spread across the low end don't answer it.
PRIMARY_SOURCE_PREFERENCE = ("epoch_ai", "evalplus")


def describe_population(source: str) -> str:
    return SOURCE_POPULATIONS.get(source, source)


def load_benchmark_scores(benchmark: Benchmark) -> Optional[BenchmarkScores]:
    """
    The distribution to measure saturation from.

    Prefers a source that tracks frontier models, falling back to the
    largest set. Returns None when nothing covers this benchmark — not a
    failure, just the boundary between measured and curated, which the
    caller is expected to report rather than paper over.
    """
    sets = load_score_sets(benchmark)
    if not sets:
        return None
    for preferred in PRIMARY_SOURCE_PREFERENCE:
        for score_set in sets:
            if score_set.source == preferred:
                return score_set
    return max(sets, key=lambda s: len(s.scores))


def load_epoch_scores(
    benchmark: Benchmark, path: Path = EPOCH_DIR
) -> Optional[BenchmarkScores]:
    """Per-model scores from Epoch AI's export, normalized to 0-1."""
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
