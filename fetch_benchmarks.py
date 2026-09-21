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
import json
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

DATA_DIR = Path(__file__).parent / "data"
EPOCH_DIR = DATA_DIR / "epoch_benchmarks"
EPOCH_METADATA_FILE = "benchmark_metadata.csv"
# Score sets pulled by fetch_benchmark_scores.py, named
# "<benchmark key>__<source>.csv" with columns model,score (0-1).
SCORES_DIR = DATA_DIR / "benchmark_scores"
SCORES_MANIFEST = SCORES_DIR / "manifest.json"

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
    # Fraction of items whose grading is wrong: mislabelled answers, tests
    # that reject correct solutions, questions with no correct option.
    # Distinct from contamination and saturation — a benchmark can be
    # fresh, unleaked, discriminating, and still scoring against a wrong
    # answer key. Populate only from a study that counted; None means
    # nobody has looked, NOT that the benchmark is clean.
    item_error_rate: Optional[float] = None
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
    #   "partial_holdout" — questions are public but the grading material
    #                      is not: hidden test cases, an unpublished rubric,
    #                      or reference solutions kept out of the public
    #                      record. Memorizing the answer key is blocked even
    #                      though the task text is crawlable.
    #   "private_holdout" — answers withheld; scoring runs server-side.
    # HF's Open ASR Leaderboard study is the argument for tracking this:
    # the models with the best scores were the most likely to reproduce
    # benchmark-specific reference errors, and their recommended fix was
    # "fully held-out evaluation sets" with temporal separation.
    # https://huggingface.co/blog/asr-benchmark-optimization
    #
    # "partial_holdout" was added after curating the 2026 benchmarks made
    # the original three values obviously too coarse: MirrorCode, DeepSWE
    # and FrontierCode all defend against leakage without being private or
    # refreshed, and were getting no credit for it. A sweep of the other
    # 19 entries found no further cases — Terminal Bench's "refresh" is
    # version churn, not a leakage defence, and HLE's held-out pool feeds
    # a rolling variant this repo may not even be scoring (see its notes).
    holdout: str = "public_static"
    # When each curated claim became publicly known, so a benchmark can be
    # scored as of a past date without using evidence from the future.
    # Keys are field names: "saturation_flagged", "contamination_rate",
    # "item_error_rate", and so on.
    #
    # This is what keeps the backtest honest. The saturation flags on the
    # four benchmarks HF retired in June 2024 are *derived from that
    # retirement*; dating them to the announcement means a backtest run at
    # 2024-06-01 cannot see them, rather than being handed its own answer.
    # A claim with no date here is treated as unknown at any past date —
    # undatable evidence can't be proven to have been available.
    evidence_dates: dict = field(default_factory=dict)
    curation_notes: str = ""

    def known_at(self, claim: str, as_of: Optional[str]) -> bool:
        """Was this claim public as of `as_of`? True when not time-travelling."""
        if as_of is None:
            return True
        date = self.evidence_dates.get(claim)
        return bool(date) and date < as_of

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
        item_error_rate=0.0649,  # Gema et al., NAACL 2025
        saturation_flagged=True,
        independent_evaluators=6,
        task_specificity=0.2,
                evidence_dates={
            # HF's retirement announcement — the backtest's ground truth, so
            # dating it here keeps it out of any pre-June-2024 scoring.
            "saturation_flagged": "2024-06-26",
            "contamination_flagged": "2025-06-13",
            "contamination_rate": "2025-06-13",  # infini-gram mini, arXiv 2506.12229
            "item_error_rate": "2024-06-06",  # MMLU-Redux, arXiv 2406.04127
        },
        curation_notes=(
            "RESEARCHED 2026-09-20. Contamination: 27.7% of MMLU items appear in "
            "DCLM-baseline. Quality: Gema et al., 'Are We Done with MMLU?' "
            "(NAACL 2025) hand-checked 5,700 questions and found a 6.49% label "
            "error rate — 57% in the Virology subset — and showed that fixing "
            "labels changes model rankings, so the noise is not symmetric — now "
            "recorded as item_error_rate=0.0649 and penalized rather than just "
            "noted. "
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
                evidence_dates={
            "contamination_flagged": "2025-06-13",
            "contamination_rate": "2025-06-13",
        },
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
                evidence_dates={
            # Flag added from 2026 leaderboard observations, not available earlier.
            "saturation_flagged": "2026-09-01",
        },
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
                evidence_dates={
            "contamination_flagged": "2024-03-06",  # arXiv 2403.04811
            "contamination_rate": "2024-03-06",
            "contamination_effect": "2024-03-06",
            # CURATE(you): the saturation flag here is reputational, with no
            # single dated source, so it is invisible to as-of scoring.
        },
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
        # A demonstrated FLOOR across all 500 problems, not a point estimate.
        # 27.6% of the benchmark was audited; 59.4% of that subset was flawed;
        # 0.594 x 138 is ~82 problems, ~16.4% of the whole 500. The other 362
        # were never audited, so the true rate is >= this and unbounded above.
        # This field holds a single number and cannot express "at least", so
        # the notes carry that and the penalty is computed from the floor.
        item_error_rate=0.164,
        saturation_flagged=False,
        independent_evaluators=5,
        task_specificity=0.95,
        evidence_dates={
            "item_error_rate": "2026-02-23",  # OpenAI's audit publication
        },
        curation_notes=(
            "RESEARCHED 2026-09-20. Human-validated subset of 500 real GitHub "
            "issues — the closest thing in this catalog to a real task, hence the "
            "0.95 specificity. Measured saturation here is already ~70%, so it is "
            "trending the way the others did. "
            "ITEM QUALITY — REVISED 2026-09-21, from 0.10 to a 0.164 FLOOR. "
            "OpenAI published an audit on 2026-02-23 ('Why SWE-bench Verified no "
            "longer measures frontier coding capabilities') covering 138 problems, "
            "27.6% of the 500, of which 59.4% had material issues in TEST DESIGN "
            "AND/OR PROBLEM DESCRIPTION. Epoch's review of that audit computes the "
            "implied floor across the whole benchmark: 0.594 x 138 is ~82 problems, "
            "~16.4% of 500, and Epoch concludes the benchmark is 'unlikely to meet "
            "our bar of fewer than 20% of questions having accuracy-impacting "
            "issues'. https://openai.com/index/why-we-no-longer-evaluate-swe-bench-verified/ "
            "| https://epoch.ai/benchmarks/swe-bench-verified/review "
            "WHY THE FLOOR AND NOT 59.4%: the 138 were chosen BECAUSE o3 failed "
            "them consistently across 64 runs. That is a deliberately hard, "
            "non-random sample, so 59.4% is the flaw rate among problems models "
            "already fail, not across the benchmark. Applying it to all 500 would "
            "assume the unaudited 362 are as broken as the hardest 138, which the "
            "evidence does not support. 16.4% is what the audit demonstrates for "
            "the whole set regardless of how the rest turn out. "
            "CURATE(you): UPPER BOUND UNKNOWN. The other 362 problems have never "
            "been audited — unknown, not clean. A random-sample audit would replace "
            "this floor with an actual estimate and is the single most valuable "
            "thing anyone could do for this entry. "
            "CURATE(you): the 18.8% 'wide tests' and 5.1% miscellaneous figures "
            "sometimes quoted for this audit could NOT be verified — OpenAI's page "
            "returns 403 to automated fetches and no reachable secondary source "
            "carried them. Only the 35.5% narrow-test figure is confirmed. "
            "OPPOSITE-DIRECTION EVIDENCE, deliberately not merged into the number "
            "above: a preprint of 2026-06-14 (arXiv 2606.16062) reports that in a "
            "49-task sample, 28.5% have test suites weak enough that a "
            "Docker-verified INCORRECT patch passes. That is false acceptance, the "
            "mirror of the false rejection the OpenAI audit measured; combining "
            "them would add two different quantities. Small sample, single source, "
            "sampling method not described. CURATE(you): if it holds up, this "
            "benchmark is wrong in both directions at once and item_error_rate as "
            "a single number may be the wrong shape for it. "
            "CORRECTION: an earlier version of this note attributed the 59.4% to "
            "UTBoost (arXiv 2506.09289). That was a conflation — the 27.6%/59.4% "
            "audit is OpenAI's. UTBoost is separate work on the same weakness. "
            "SEPARATE FINDING, NOT ACTED ON: the same OpenAI post reports that "
            "every frontier model tested could reproduce verbatim gold patches or "
            "problem-specific details, i.e. direct contamination evidence. This "
            "entry still carries contamination_flagged=False. Changing that is a "
            "scoring decision outside the scope of the commit that revised "
            "item_error_rate, and is flagged for a deliberate call."
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
        item_error_rate=0.36,  # Surge AI audit
        saturation_flagged=True,
        independent_evaluators=5,
        task_specificity=0.2,
                evidence_dates={
            "saturation_flagged": "2024-06-26",  # HF retirement
            "item_error_rate": "2022-11-30",  # Surge AI audit
        },
        curation_notes=(
            "RESEARCHED 2026-09-20. Retired from HF's Open LLM Leaderboard in June "
            "2024, explicitly because the v1 set had saturated — models scored high "
            "enough that it stopped separating them. 2019 vintage, so assume it is "
            "in every crawl. Kept here as the calibration point for 'do not trust'. "
            "ITEM QUALITY (added 2026-09-20): a Surge AI audit found errors in 36% "
            "of rows — mislabelled endings, ungrammatical text, items with no "
            "correct answer. Recorded as item_error_rate=0.36. A later academic "
            "analysis ('What the HellaSwag?', arXiv 2504.07825) is harsher still, "
            "reporting under 10% of a sample as fully valid; the 36% figure is used "
            "as the better-attested and more conservative of the two. "
            "https://huggingface.co/docs/leaderboards/en/open_llm_leaderboard/archive | "
            "https://surgehq.ai/blog/hellaswag-or-hellabad-36-of-this-popular-llm-benchmark-contains-errors"
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
                evidence_dates={
            # Both flags come from this repo's own 2026 measurement. In June
            # 2024 BBH was a *replacement* benchmark, not a suspect one.
            "saturation_flagged": "2026-09-20",
            "contamination_flagged": "2026-09-20",
        },
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
        # Corrected 2026-09-20: this said False while the notes recorded the
        # June 2024 retirement for saturation, and the measured reading is
        # 87%. Caught by a backtest leakage test, not by inspection.
        saturation_flagged=True,
        independent_evaluators=4,
        task_specificity=0.4,
                evidence_dates={
            "saturation_flagged": "2024-06-26",  # HF retirement
        },
        curation_notes=(
            "RESEARCHED 2026-09-20. Retired from HF's Open LLM Leaderboard in June "
            "2024 with the rest of the v1 set — which is why saturation_flagged is "
            "True; it read False until a backtest test noticed the contradiction "
            "with these notes. Note it measures imitation of common "
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
                evidence_dates={
            "saturation_flagged": "2024-06-26",  # HF retirement
        },
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
        dataset_size=30,  # 15 target programs x 2 implementation languages
        contamination_flagged=False,
        saturation_flagged=False,
        independent_evaluators=1,
        task_specificity=0.8,
        holdout="partial_holdout",  # ~34% of tests held out
        curation_notes=(
            "RESEARCHED 2026-09-20. Epoch AI's long-horizon coding benchmark, "
            "co-developed with METR. Models reimplement CLI programs from "
            "execute-only access plus docs — no source, no internet — across Unix "
            "utilities, serialization tools, bioinformatics, interpreters, static "
            "analysis, cryptography and compression. 25 target programs exist; the "
            "leaderboard config scores the 15 Medium/Large ones in two languages = "
            "30 tasks. Specificity 0.8: reimplementation is a real engineering "
            "capability but a constructed exercise, not a task someone had anyway. "
            "Evaluators lowered 2 -> 1: Epoch publishes the scores and METR "
            "co-built it, so they are not independent of each other. "
            "Leakage defence: ~34% of each program's test cases are held out, "
            "which blocks memorizing solutions without making the benchmark "
            "private or refreshed. Recorded as holdout='partial_holdout'. "
            "https://epoch.ai/benchmarks/mirrorcode "
            "CURATE(you): Epoch dates it 2026-06-26 but the citation says "
            "published August 2026 — check which is the public release."
        ),
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
        independent_evaluators=2,
        task_specificity=0.7,
        curation_notes=(
            "RESEARCHED 2026-09-20. The 225 hardest of Exercism's 697 exercises — "
            "specifically those solved by 3 or fewer models — in C++, Go, Java, "
            "JavaScript, Python and Rust. Worth noting WHY it exists: aider's "
            "earlier Python-only benchmark saturated above 80%, so this is a "
            "de-saturation successor, the same pattern as MMLU -> MMLU-Pro. "
            "Specificity cut 0.85 -> 0.7: Exercism katas are self-contained "
            "puzzles, not real code; what does transfer is that the model must "
            "produce a correctly-formatted edit to an existing file. Evaluators "
            "cut 3 -> 2 (aider's leaderboard, Epoch) — the rest are aggregators "
            "republishing aider's numbers, which is not independent measurement. "
            "https://aider.chat/2024/12/21/polyglot.html"
        ),
        epoch_source_file="aider_polyglot_external.csv",
    ),
    Benchmark(
        key="terminal_bench",
        name="Terminal Bench",
        category="agentic tool use",
        aliases=("TerminalBench", "terminalbench", "terminalbench_hard"),
        release_date="2025-05-19",  # was 2025-05-01: corrected, public introduction date
        dataset_size=80,  # Terminal-Bench-Core at the 2025-05-19 release
        contamination_flagged=False,
        saturation_flagged=False,
        independent_evaluators=3,
        task_specificity=0.9,
        curation_notes=(
            "RESEARCHED 2026-09-20. Introduced 2025-05-19 by Stanford (Mike A. "
            "Merrill) and the Laude Institute (Alexander G. Shaw), alongside the "
            "Terminus agent. The launch set, Terminal-Bench-Core, had 80 tasks in "
            "a Docker sandbox. Specificity 0.9: real sysadmin, data-processing, "
            "training and security work done at a shell. Evaluators = 3 (official "
            "leaderboard, Epoch, Artificial Analysis). "
            "HARNESS/VERSION NOT PINNED — CURATE(you): the benchmark has moved "
            "fast. 2.0 shipped November 2025; 2.1 is a verified refresh of 89 "
            "tasks run with the Terminus 2 harness in an e2b sandbox, and "
            "Artificial Analysis separately publishes Terminal-Bench Hard. Epoch's "
            "file gives a release date of 2025-05-19 and an 'Accuracy mean' "
            "column but does not name the version or harness, so the scores this "
            "repo reads MAY MIX HARNESSES. Scores are known to move between "
            "harnesses, so treat cross-model comparisons here as provisional until "
            "the version is confirmed."
        ),
        epoch_source_file="terminalbench_external.csv",
    ),
    Benchmark(
        key="gso_bench",
        name="GSO-Bench",
        category="software engineering",
        aliases=("GSO", "gso_external"),
        release_date="2025-05-29",  # was 2025-07-01: wrong, corrected from arXiv + Epoch
        dataset_size=102,
        contamination_flagged=False,
        saturation_flagged=False,
        independent_evaluators=2,
        task_specificity=0.9,
        curation_notes=(
            "RESEARCHED 2026-09-20. 102 software *optimization* tasks across 10 "
            "real codebases — arXiv 2505.23671, NeurIPS 2025 D&B. The agent gets a "
            "codebase and a performance test, and must beat or match the expert "
            "developer's own optimization commit. The Opt@1 scorer this repo reads "
            "is the fraction of tasks where one attempt achieves >=95% of the human "
            "speedup AND passes correctness; p=0 would score correctness alone. "
            "Specificity raised 0.85 -> 0.9: the reference is a real commit a real "
            "maintainer wrote. Leading agents score under 5%, which is consistent "
            "with the ~15% saturation measured here. Evaluators = 2 (authors, Epoch). "
            "https://arxiv.org/abs/2505.23671 | https://gso-bench.github.io/"
        ),
        epoch_source_file="gso_external.csv",
    ),
    Benchmark(
        key="deepswe",
        name="DeepSWE",
        category="software engineering",
        aliases=("Deep SWE",),
        release_date="2026-05-26",
        dataset_size=113,
        contamination_flagged=False,
        saturation_flagged=False,
        independent_evaluators=2,
        task_specificity=0.9,
        holdout="partial_holdout",  # reference solutions never published upstream
        curation_notes=(
            "RESEARCHED 2026-09-20. 113 original long-horizon engineering tasks "
            "written from scratch across 91 open-source repos in five languages "
            "(arXiv 2607.07946). Two design choices matter here: the tasks are "
            "NEVER CONTRIBUTED UPSTREAM, so reference solutions stay outside the "
            "public record training scrapes; and grading uses hand-written "
            "verifiers that accept any working implementation instead of the "
            "repo's own tests. On the second point they report an independent LLM "
            "judge disagreeing with their verifier 1.4% of the time against 32.4% "
            "for SWE-bench Pro's inherited tests — i.e. much of what SWE-bench-"
            "style benchmarks score as failure is the test being wrong, not the "
            "patch. Specificity 0.9 stands. Evaluators = 2 (authors, Epoch). "
            "Unpublished reference solutions are a real leakage defence — "
            "recorded as holdout='partial_holdout'. Note this is the strongest "
            "form of the three: the answers were never public at all, rather "
            "than public-but-partially-hidden. "
            "NAME COLLISION — CURATE(you): 'DeepSWE-Preview' is a 32B coding MODEL "
            "from Agentica/Together AI (July 2025), unrelated to this benchmark. "
            "The alias 'Deep SWE' could pick up model scores; worth tightening. "
            "Also: Epoch dates this 2026-05-26 while the paper was submitted "
            "2026-07-08 — the discrepancy is unexplained, Epoch's date kept."
        ),
        epoch_source_file="deepswe_external.csv",
    ),
    Benchmark(
        key="frontiercode",
        name="FrontierCode",
        category="code generation",
        aliases=("Frontier Code",),
        release_date="2026-06-08",
        dataset_size=150,  # Extended set; the Main subset scored here is 100
        contamination_flagged=False,
        saturation_flagged=False,
        independent_evaluators=2,
        task_specificity=0.95,
        holdout="partial_holdout",  # held-out tests + unpublished maintainer rubric
        curation_notes=(
            "RESEARCHED 2026-09-20. Built by COGNITION, not Epoch — Epoch charts "
            "Cognition's public leaderboard, currently revision 1.1. Each task pairs "
            "a checked-out repo with one real open-source issue; patches are graded "
            "against held-out tests AND a maintainer-authored rubric covering "
            "behavioural correctness, regression safety, build/style cleanliness and "
            "project conventions. The score this repo reads is the Main subset (100 "
            "hardest of 150). Specificity raised 0.8 -> 0.95: 'would a maintainer "
            "merge this?' is the actual job, not a proxy for it. Evaluators = 2 "
            "(Cognition, Epoch). "
            "Leakage defence: graded against held-out tests plus a rubric that "
            "is not published, so neither the tests nor the grading criteria can "
            "be memorized. Recorded as holdout='partial_holdout'. "
            "https://epoch.ai/benchmarks/frontiercode"
        ),
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
                evidence_dates={
            "saturation_flagged": "2026-09-20",  # this repo's measurement
            # CURATE(you): Epoch's contamination warning carries no date I
            # could pin, so it is excluded from as-of scoring.
        },
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
        independent_evaluators=3,
        task_specificity=0.35,
        curation_notes=(
            "RESEARCHED 2026-09-20. 2,500 expert-written questions across many "
            "subjects, from the Center for AI Safety and Scale AI, public January "
            "2025 (arXiv 2501.14249). Specificity stays low at 0.35: it is "
            "deliberately an exam of exotic expert knowledge, not a task anyone "
            "performs — which is the point, and also why a high score transfers "
            "poorly. Evaluators trimmed 4 -> 3 (Scale's leaderboard, Epoch, "
            "Artificial Analysis). "
            "https://arxiv.org/abs/2501.14249 | https://epoch.ai/benchmarks/hle "
            "CURATE(you): an HLE-Rolling variant replaces solved questions from a "
            "held-out pool. That would change the holdout classification, but I "
            "could not confirm whether Epoch's scores here are the static 2,500 or "
            "the rolling set — left as public_static until that is settled."
        ),
        epoch_source_file="hle_external.csv",
    ),
    Benchmark(
        key="simpleqa_verified",
        name="SimpleQA Verified",
        category="factual accuracy",
        # NOTE: "SimpleQA" deliberately removed as an alias — see notes.
        aliases=("simpleqa_verified", "SimpleQA-Verified"),
        release_date="2025-09-09",  # was 2024-10-30, which is OpenAI's SimpleQA, a different benchmark
        dataset_size=1000,
        contamination_flagged=False,
        saturation_flagged=False,
        independent_evaluators=2,
        task_specificity=0.6,
        curation_notes=(
            "RESEARCHED 2026-09-20. Two corrections, one of which was a live bug. "
            "(1) The date was wrong: this is Google DeepMind's SimpleQA Verified, "
            "arXiv 2509.07968, September 2025 — not OpenAI's SimpleQA (Wei et al., "
            "October 2024), which is a different benchmark. Epoch's metadata agrees "
            "(2025-09-09). (2) 'SimpleQA' was listed as an ALIAS, so any source "
            "reporting OpenAI's SimpleQA would have had its scores attributed to "
            "this benchmark. Alias removed. "
            "1,000 prompts, rebuilt from SimpleQA to fix noisy labels, topical bias "
            "and question redundancy. Specificity cut 0.7 -> 0.6: short-form "
            "parametric factuality is a real property of a model but not a task a "
            "user performs. Evaluators = 2 (Google/Kaggle leaderboard, Epoch). "
            "https://arxiv.org/abs/2509.07968"
        ),
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
        independent_evaluators=2,
        task_specificity=0.9,
        curation_notes=(
            "RESEARCHED 2026-09-20. 369 real computer-use tasks on Ubuntu/Windows/"
            "macOS spanning OS file I/O, LibreOffice, Chrome, VLC, Thunderbird, "
            "VS Code, GIMP and multi-app workflows — arXiv 2404.07972, NeurIPS "
            "2024. Each task ships an initial-state setup and an execution-based "
            "verification script, so grading is behavioural rather than textual. "
            "Specificity 0.9 stands: these are literally things people do on a "
            "computer. Evaluators cut 3 -> 2 (authors' leaderboard, Epoch) — labs "
            "quote OSWorld in model cards, but self-reported numbers are not an "
            "independent evaluator. "
            "https://arxiv.org/abs/2404.07972 "
            "CURATE(you): scores move a lot with the agent scaffold, and OSWorld-V2 "
            "now exists — check which Epoch's runs use before comparing across time."
        ),
        epoch_source_file="os_world_external.csv",
    ),
    Benchmark(
        key="the_agent_company",
        name="The Agent Company",
        category="agentic tool use",
        aliases=("TheAgentCompany", "the_agent_company_external"),
        release_date="2024-12-18",
        dataset_size=175,
        contamination_flagged=False,
        saturation_flagged=False,
        independent_evaluators=2,
        task_specificity=0.85,
        curation_notes=(
            "RESEARCHED 2026-09-20. 175 professional tasks inside a simulated "
            "software company — CMU and Duke, arXiv 2412.14161, NeurIPS 2025 "
            "Datasets & Benchmarks. Agents work against real self-hosted tools "
            "rather than mock APIs, which is why specificity is high; trimmed 0.9 "
            "-> 0.85 because the company and its employees are simulated, so the "
            "social and organizational parts are staged. Evaluators = 2 (the "
            "authors' leaderboard, Epoch). "
            "https://arxiv.org/abs/2412.14161 | https://the-agent-company.com/"
        ),
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
        independent_evaluators=3,
        task_specificity=0.3,
                evidence_dates={
            # CURATE(you): contamination here is assumed from the 2017 web
            # provenance, with no dated study, so as-of scoring ignores it.
        },
        curation_notes=(
            "RESEARCHED 2026-09-20. Joshi et al., ACL 2017 (arXiv 1705.03551): "
            "95K question-answer pairs written by trivia enthusiasts, with 650K+ "
            "question-answer-evidence triples once the ~6 evidence documents per "
            "question are counted. dataset_size records the 95K questions. Public "
            "since 2017 and web-sourced, so contamination is assumed rather than "
            "measured — no study quantifying its overlap found, which is why "
            "contamination_rate stays None and the flat penalty applies. "
            "Specificity 0.3: recall of web trivia is a proxy for parametric "
            "knowledge, not a task. Evaluators = 3, a soft count (original "
            "authors, Epoch, HF Open LLM Leaderboard v1 era) — CURATE(you), few "
            "current leaderboards still run it. "
            "https://aclanthology.org/P17-1147/"
        ),
        epoch_source_file="trivia_qa_external.csv",
    ),
)


@dataclass
class BenchmarkScores:
    """Per-model scores for one benchmark, normalized to 0-1."""

    benchmark_key: str
    scores: list[float] = field(default_factory=list)
    model_names: list[str] = field(default_factory=list)
    # Per-model dates, "" where the source publishes none. Parallel to
    # `scores`; this is what lets a benchmark be scored as of a past date.
    model_dates: list[str] = field(default_factory=list)
    ceiling: float = 1.0
    random_baseline: float = 0.0
    source: str = "epoch_ai"
    # "none" | "baseline" | "length" — see fetch_benchmark_scores. Only
    # sets sharing a normalization are comparable model-for-model.
    normalization: str = "none"

    @property
    def dated(self) -> int:
        return sum(1 for d in self.model_dates if d)

    def before(self, cutoff: str) -> "BenchmarkScores":
        """
        The same set restricted to models dated before `cutoff`.

        Undated models are DROPPED rather than assumed old: including a
        model that might postdate the cutoff would leak the future into a
        backtest, which is the one thing a backtest must not do. A set
        with no dates at all therefore comes back empty, and the caller
        is expected to notice rather than score an empty distribution.
        """
        keep = [
            i
            for i, date in enumerate(self.model_dates)
            if date and date < cutoff
        ]
        return BenchmarkScores(
            benchmark_key=self.benchmark_key,
            scores=[self.scores[i] for i in keep],
            model_names=[self.model_names[i] for i in keep],
            model_dates=[self.model_dates[i] for i in keep],
            ceiling=self.ceiling,
            random_baseline=self.random_baseline,
            source=self.source,
            normalization=self.normalization,
        )


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


def _scores_manifest(path: Path = SCORES_MANIFEST) -> dict[str, dict]:
    """Per-set provenance written by fetch_benchmark_scores.py."""
    if not path.exists():
        return {}
    try:
        return (json.loads(path.read_text()) or {}).get("sets", {})
    except (json.JSONDecodeError, OSError):
        return {}


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
        dates: list[str] = []
        with file_path.open(newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                try:
                    scores.append(float(row["score"]))
                except (KeyError, TypeError, ValueError):
                    continue
                names.append((row.get("model") or "").strip())
                dates.append((row.get("date") or "").strip())
        if scores:
            # The manifest carries the random baseline and which
            # normalization (if any) the column used. Without it every set
            # would be treated as a plain 0-1 accuracy, which is how
            # baseline-normalized GPQA scores once got read as raw ones.
            meta = _scores_manifest().get(f"{benchmark.key}__{source}", {})
            sets.append(
                BenchmarkScores(
                    benchmark_key=benchmark.key,
                    scores=scores,
                    model_names=names,
                    model_dates=dates,
                    ceiling=float(meta.get("ceiling", 1.0)),
                    random_baseline=float(meta.get("random_baseline", 0.0)),
                    source=source,
                    normalization=str(meta.get("normalization", "none")),
                )
            )
    return sets


@lru_cache(maxsize=None)
def _cached_score_sets(key: str) -> tuple:
    """
    Score sets by benchmark key, read once per process.

    The leaderboard exports run to thousands of rows and every factor
    that touches them would otherwise re-parse the CSV. Callers treat
    these as read-only; mutating a returned set would corrupt the cache.
    """
    benchmark = find_benchmark(key)
    if benchmark is None:
        return ()
    sets = load_external_score_sets(benchmark)
    epoch = load_epoch_scores(benchmark)
    if epoch is not None:
        sets.insert(0, epoch)
    return tuple(sets)


def load_score_sets(benchmark: Benchmark) -> list[BenchmarkScores]:
    """Every score distribution available for this benchmark, any source."""
    return list(_cached_score_sets(benchmark.key))





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
    dates: list[str] = []
    with file_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        date_column = next(
            (c for c in (reader.fieldnames or []) if c.strip().lower() == "release date"),
            None,
        )
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
            dates.append((row.get(date_column) or "").strip()[:10] if date_column else "")

    if not scores:
        return None
    return BenchmarkScores(
        benchmark_key=benchmark.key,
        scores=scores,
        model_names=names,
        model_dates=dates,
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
