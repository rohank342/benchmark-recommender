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
    # Added 2026-09-21 with IFEval. Following explicit, checkable
    # instructions is a distinct property from reasoning or knowledge, and
    # none of the categories above covered it without distortion.
    # task_matcher.py needed new vocabulary to match it.
    "instruction following",
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
    # WHAT KIND of effect measurement it is. Same pattern as
    # item_error_rate_basis, and for the same reason: two numbers of the
    # same magnitude can mean different things.
    #
    #   "difficulty_controlled" — the comparison set was built to match
    #       the original's difficulty, so the drop is close to pure
    #       contamination. GSM1k did this deliberately (human solve
    #       rates, solution steps, answer magnitude).
    #   "uncontrolled" — the comparison set is harder, easier, or
    #       unknown, so the drop mixes memorization with difficulty.
    #       EvoEval's LLM-evolved variants of HumanEval are this.
    #
    # SCORING IS IDENTICAL for both, deliberately. Discounting an
    # uncontrolled figure would mean inventing a correction nobody has
    # measured. What this changes is what the tool SAYS, so a reader can
    # tell a 39% that may be mostly difficulty from a 5% that is not.
    # Default is "uncontrolled": assuming a study controlled for
    # difficulty when nobody checked is the optimistic error.
    contamination_effect_basis: str = "uncontrolled"
    # Fraction of items whose grading is wrong: mislabelled answers, tests
    # that reject correct solutions, questions with no correct option.
    # Distinct from contamination and saturation — a benchmark can be
    # fresh, unleaked, discriminating, and still scoring against a wrong
    # answer key. Populate only from a study that counted; None means
    # nobody has looked, NOT that the benchmark is clean.
    item_error_rate: Optional[float] = None
    # What kind of number item_error_rate is:
    #   "estimate"    — a measurement of the whole benchmark, or a random
    #                   sample intended to stand for it. The default,
    #                   because that is what most audits report.
    #   "lower_bound" — a floor. The audit demonstrated at least this much
    #                   and the rest of the benchmark was never examined,
    #                   so the true rate is >= the recorded value and
    #                   unbounded above.
    # SCORING IS DELIBERATELY IDENTICAL for both. A floor of 16% and an
    # estimate of 16% carry the same penalty, because the alternative —
    # inflating a bound into a worst case — would be inventing a number
    # the evidence does not contain. What this field changes is what the
    # tool SAYS: "at least 16% of items are mislabelled" rather than
    # "16% of items are mislabelled". The distinction is real and a reader
    # deserves it, but it is a claim about precision, not about severity,
    # and precision is not something the four factors price.
    item_error_rate_basis: str = "estimate"
    # Publicly discussed as saturated. Note this is the *reported* status;
    # benchmark_scoring.py also measures saturation where data allows, and
    # the two disagreeing is itself informative.
    saturation_flagged: bool = False
    # Independent evaluators/leaderboards publishing scores on it.
    independent_evaluators: int = 1
    # How narrowly this maps to one real task, as five rubric dimensions
    # scored 0/1/2 — see docs/SPECIFICITY_RUBRIC.md (v2, adopted by the
    # owner 2026-09-21):
    #
    #   A  item provenance    synthetic / written for the test / real artifact
    #   B  output and check   does success here look like success outside?
    #                         mixed cases take the LOWER of the two halves
    #   C  scope              catch-all / one domain / job-nameable task type
    #   D  who does this      nobody / a component of work / somebody's output
    #   E  scale              one shot / multi-step / spans files and turns
    #
    # `task_specificity` is COMPUTED from these (sum / 10) rather than
    # stored, so no value can move without a judgement moving that says
    # why. This is the only factor with no measurement behind it, so the
    # decomposition is the whole of its accountability.
    specificity_dimensions: Optional[tuple[int, int, int, int, int]] = None

    @property
    def task_specificity(self) -> float:
        """0-1, derived from the rubric. Never stored directly."""
        return specificity_from(self.specificity_dimensions)
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


# The five rubric dimensions, in order, as stored in
# Benchmark.specificity_dimensions.
SPECIFICITY_DIMENSIONS = ("provenance", "output_and_check", "scope", "who", "scale")
SPECIFICITY_MAX = 2 * len(SPECIFICITY_DIMENSIONS)  # 10


def specificity_from(dimensions: Optional[tuple[int, ...]]) -> float:
    """
    Rubric v2: five dimensions scored 0-2, specificity = sum / 10.

    A missing scoring is an error, not a default. 0.5 would be a number
    nobody assigned — exactly the kind of invented value the evidence
    standard exists to prevent — so there is no fallback and a test
    enforces that every catalog entry carries its five scores.
    """
    if dimensions is None:
        raise ValueError(
            "specificity_dimensions is unset: score the benchmark against "
            "docs/SPECIFICITY_RUBRIC.md rather than inventing a value"
        )
    if len(dimensions) != len(SPECIFICITY_DIMENSIONS):
        raise ValueError(
            f"expected {len(SPECIFICITY_DIMENSIONS)} dimensions, got {len(dimensions)}"
        )
    if any(d not in (0, 1, 2) for d in dimensions):
        raise ValueError(f"rubric dimensions are scored 0, 1 or 2; got {dimensions}")
    return sum(dimensions) / SPECIFICITY_MAX


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
        specificity_dimensions=(2, 0, 0, 0, 0),
                evidence_dates={
            # HF's retirement announcement — the backtest's ground truth, so
            # dating it here keeps it out of any pre-June-2024 scoring.
            "saturation_flagged": "2024-06-26",
            "contamination_flagged": "2025-06-13",
            "contamination_rate": "2025-06-13",  # infini-gram mini, arXiv 2506.12229
            "item_error_rate": "2024-06-06",  # MMLU-Redux, arXiv 2406.04127
        },
        curation_notes=(
            "SPECIFICITY: Rubric v2, applied by Claude Code 2026-09-21, adopted by owner 2026-09-21. Not independently checked: a second reviewer scoring a sample would be the validation. "
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
        specificity_dimensions=(2, 0, 0, 0, 0),
                evidence_dates={
            "contamination_flagged": "2025-06-13",
            "contamination_rate": "2025-06-13",
        },
        curation_notes=(
            "SPECIFICITY: Rubric v2, applied by Claude Code 2026-09-21, adopted by owner 2026-09-21. Not independently checked: a second reviewer scoring a sample would be the validation. "
            "RESEARCHED 2026-09-20. Built to de-saturate MMLU (10 options, harder "
            "distractors) and picked for HF's Open LLM Leaderboard v2 in June 2024. "
            "Contamination: 16.2% dirty against DCLM-baseline — better than MMLU's "
            "27.7%, not clean. Saturation: reported frontier clustering within ~5 "
            "points (83-90%), which is tighter than GPQA Diamond's 15-point spread; "
            "SATURATION IS MEASURED — corrected 2026-09-23, owner-authorized. "
            "This read: 'CURATE(you) — that is a secondhand figure, and with no "
            "Epoch score file it can't be measured here. Finding a leaderboard "
            "export is the fix.' The export was found. Saturation is 0.158 over "
            "4,575 rows from the HF Open LLM Leaderboard v2 export "
            "(data/benchmark_scores/mmlu_pro__open_llm_leaderboard_v2.csv, column "
            "MMLU-PRO Raw) and the discrimination factor carries basis='measured'. "
            "THE MEASUREMENT DOES NOT CORROBORATE THE SECONDHAND FIGURE and must "
            "not be written as though it did: the 83-90% frontier clustering above "
            "describes a FRONTIER population, while 0.158 is the OPEN COMMUNITY "
            "population. Those answer different questions — GPQA Diamond reads "
            "0.664 on frontier models against 0.190 on the community leaderboard. "
            "The secondhand claim is still uncorroborated in-repo. CURATE(you): a "
            "frontier-population export would settle it; the v2 reading cannot. "
            "FURTHER CAVEAT 2026-09-23: 79 of those 4,575 rows are the same model "
            "at a second precision, so the distinct-model population is 4,496. The "
            "reading may move when a collapsing rule is chosen — docs/CONFIG_ROWS.md."
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
        specificity_dimensions=(1, 0, 1, 0, 0),
                evidence_dates={
            # Flag added from 2026 leaderboard observations, not available earlier.
            "saturation_flagged": "2026-09-01",
        },
        curation_notes=(
            "SPECIFICITY: Rubric v2, applied by Claude Code 2026-09-21, adopted by owner 2026-09-21. Not independently checked: a second reviewer scoring a sample would be the validation. "
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
        specificity_dimensions=(1, 2, 2, 1, 0),
                evidence_dates={
            "contamination_flagged": "2024-03-06",  # arXiv 2403.04811
            "contamination_rate": "2024-03-06",
            "contamination_effect": "2024-03-06",
            # CURATE(you): the saturation flag here is reputational, with no
            # single dated source, so it is invisible to as-of scoring.
        },
        curation_notes=(
            "SPECIFICITY: Rubric v2, applied by Claude Code 2026-09-21, adopted by owner 2026-09-21. Not independently checked: a second reviewer scoring a sample would be the validation. "
            "RESEARCHED 2026-09-20. The canonical case for this project. "
            "Contamination is quantified, not just suspected: 8-18% of items appear "
            "in major open-weight pretraining corpora, and across 51 LLMs scores "
            "fall by an average of 39.4% on EvoEval. 164 short functions, public "
            "since 2021. https://arxiv.org/pdf/2403.04811 "
            "CITATION CORRECTED 2026-09-21. The 39.4%/51-LLM figure was previously "
            "attributed to the two papers cited here. It is in NEITHER. Riddell et "
            "al. (2403.04811) covers 12 models across three families and reports "
            "relative degradations of 25.9%, 57.1% and 43.2% for HumanEval at the "
            "exact-match threshold; Bradbury and More (2412.01526) covers four "
            "models with 4.75-13.75 point drops. The 39.4% across 51 LLMs is "
            "EvoEval (Xia et al.). The overlap-rate range does come from Riddell. "
            "CURATE(you): 0.394 IS NOT A CLEAN CONTAMINATION EFFECT. EvoEval "
            "problems are LLM-evolved transformations of HumanEval problems with no "
            "control for difficulty, so the drop mixes memorization with the new "
            "problems simply being harder. GSM8K 0.051 — from GSM1k, which WAS "
            "difficulty-matched by construction — is a cleaner measurement of the "
            "same field, which means this field currently holds two different "
            "quantities and the penalty formula cannot tell them apart. Fixing it "
            "means finding a difficulty-controlled variant for HumanEval "
            "(HumanEval+ is the obvious candidate), not adjusting 0.394. "
            "INVESTIGATED 2026-09-22 AND NOT RESOLVED. Riddell et al. Table 3 "
            "decouples memorization from difficulty by comparing accuracy on "
            "the STACK-overlapping subset (DS, 31 of 164) against its "
            "complement, for models trained on the STACK and models trained on "
            "the PILE. Difference-in-differences on those four rows gives +8.1 "
            "points of contamination-attributable gap (exposed mean +41.5, "
            "control mean +33.4). THAT NUMBER IS NOT USABLE: the control is not "
            "unexposed. The paper reports |DS n P| = 16, so 16 of the 31 "
            "STACK-overlapping problems are ALSO in the PILE — 52% of the "
            "control group saw the material it is supposed to control for. "
            "The design cannot separate 'the subset is easier' from 'both "
            "groups are contaminated', and the two have opposite implications. "
            "So 0.394 stands, with contamination_effect_basis=\'uncontrolled\'. "
            "What would settle it: an unexposed control (a model whose training "
            "corpus provably excludes both), or a difficulty-matched fresh set "
            "for HumanEval in the way GSM1k is for GSM8K. Neither exists. "
            "SATURATION IS NOW MEASURED — corrected 2026-09-23, owner-authorized. "
            "This note previously read \'saturation is still ASSERTED here, not "
            "measured — no Epoch score file\'. That is out of date: HumanEval has "
            "no Epoch file, but it has an EvalPlus one. Saturation is computed "
            "from data/benchmark_scores/humaneval__evalplus.csv — 125 models, "
            "greedy-decoding pass@1 pulled from evalplus.github.io/results.json "
            "by fetch_benchmark_scores.fetch_evalplus, recorded in the score "
            "manifest — and the discrimination factor carries basis=\'measured\' "
            "(0.438 saturation; python probes/findings.py humaneval). "
            "STILL OUTSTANDING, and it is what the old note was really asking "
            "for: the 39.4% EvoEval figure is cited, not reproduced in-repo. "
            "The EvalPlus export supplies the score DISTRIBUTION, not EvoEval\'s "
            "per-model drops, so reproducing 0.394 would need an EvoEval export "
            "of its own."
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
        specificity_dimensions=(2, 2, 2, 1, 0),
        holdout="refreshed",
        curation_notes=(
            "SPECIFICITY: Rubric v2, applied by Claude Code 2026-09-21, adopted by owner 2026-09-21. Not independently checked: a second reviewer scoring a sample would be the validation. "
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
        # Set 2026-09-21 on OpenAI's own report (2026-02-23) that every
        # frontier model it tested could reproduce the gold patch verbatim.
        # Rate and effect stay None: the post gives neither, and None here
        # means "nobody has quantified it", which is the truth.
        contamination_flagged=True,
        # A demonstrated FLOOR across all 500 problems, not a point estimate.
        # 27.6% of the benchmark was audited; 59.4% of that subset was flawed;
        # 0.594 x 138 is ~82 problems, ~16.4% of the whole 500. The other 362
        # were never audited, so the true rate is >= this and unbounded above.
        item_error_rate=0.164,
        item_error_rate_basis="lower_bound",
        saturation_flagged=False,
        independent_evaluators=5,
        specificity_dimensions=(2, 2, 2, 2, 2),
        evidence_dates={
            "item_error_rate": "2026-02-23",  # OpenAI's audit publication
            # Same post, same date. Postdates the 2024-06-01 backtest
            # cutoff by 20 months, and the benchmark postdates it too.
            "contamination_flagged": "2026-02-23",
        },
        curation_notes=(
            "SPECIFICITY: Rubric v2, applied by Claude Code 2026-09-21, adopted by owner 2026-09-21. Not independently checked: a second reviewer scoring a sample would be the validation. "
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
            "THE 59.4% BREAKS DOWN INTO THREE SPLITS, all three now recorded "
            "(2026-09-21): 35.5% of the audited tasks have strict tests that "
            "enforce specific implementation details (narrow tests); 18.8% have "
            "tests checking for additional functionality that the problem "
            "statement never specified (wide tests); the remaining 5.1% had "
            "miscellaneous issues. 35.5 + 18.8 + 5.1 = 59.4, which closes exactly "
            "against the headline figure. The two main modes point opposite ways — "
            "narrow tests reject correct patches over implementation style, wide "
            "tests demand behaviour nobody asked for — so this is not one defect "
            "measured once. Source: "
            "https://openai.com/index/why-we-no-longer-evaluate-swe-bench-verified/ "
            "SOURCING CAVEAT: openai.com returns 403 to automated fetches, so this "
            "repo cannot cite that page by retrieval. The text was obtained via "
            "web search — by the owner, and re-confirmed here against a secondary "
            "carrier quoting the three sentences verbatim. The citation is the "
            "primary source the wording comes from, not a page this repo fetched. "
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
            "CONTAMINATION — FLAGGED 2026-09-21, evidence dated 2026-02-23. The "
            "same OpenAI post reports that 'all frontier models we tested were "
            "able to reproduce the original, human-written bug fix used as the "
            "ground-truth reference, known as the gold patch, or verbatim problem "
            "statement specifics for certain tasks'. That is direct memorization "
            "evidence from the lab that built the models and commissioned the "
            "benchmark's verified subset, i.e. a source arguing against its own "
            "flagship number. It is stronger evidence than the n-gram overlap "
            "studies behind most other flags in this catalog. Flagged on a "
            "deliberate call, in its own commit, separate from the item_error_rate "
            "revision it was found alongside. "
            "CURATE(you): NO RATE AND NO EFFECT. contamination_rate and "
            "contamination_effect stay None because the post quantifies neither — "
            "it does not say how many of the 500 are reproducible, nor how far "
            "scores fall without them. So this entry takes the flat flagged "
            "penalty rather than a scaled one, which is the coarsest treatment "
            "the scorer has. What would replace it: a count of tasks whose gold "
            "patch a model emits verbatim (-> rate), or a re-run on rewritten "
            "problems (-> effect). 'All frontier models could do it for certain "
            "tasks' is unbounded in both directions and must not be read as 1.0. "
            "WHY THIS COMPOUNDS: the same tasks are now penalized for being "
            "memorized AND for being misgraded. Those are independent defects "
            "with independent evidence, but they come from one audit of one "
            "non-random 138-problem sample, so they are not independent "
            "OBSERVATIONS. Two multiplicative penalties from one study may "
            "double-count; the scorer has no way to express that and this note "
            "is the only record of it."
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
        specificity_dimensions=(0, 0, 1, 0, 0),
                evidence_dates={
            "saturation_flagged": "2024-06-26",  # HF retirement
            "item_error_rate": "2022-11-30",  # Surge AI audit
        },
        curation_notes=(
            "SPECIFICITY: Rubric v2, applied by Claude Code 2026-09-21, adopted by owner 2026-09-21. Not independently checked: a second reviewer scoring a sample would be the validation. "
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
        specificity_dimensions=(1, 1, 0, 0, 1),
                evidence_dates={
            # Both flags come from this repo's own 2026 measurement. In June
            # 2024 BBH was a *replacement* benchmark, not a suspect one.
            "saturation_flagged": "2026-09-20",
            "contamination_flagged": "2026-09-20",
        },
        curation_notes=(
            "SPECIFICITY: Rubric v2, applied by Claude Code 2026-09-21, adopted by owner 2026-09-21. Not independently checked: a second reviewer scoring a sample would be the validation. "
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
        specificity_dimensions=(1, 0, 1, 0, 0),
                evidence_dates={
            "saturation_flagged": "2024-06-26",  # HF retirement
        },
        curation_notes=(
            "SPECIFICITY: Rubric v2, applied by Claude Code 2026-09-21, adopted by owner 2026-09-21. Not independently checked: a second reviewer scoring a sample would be the validation. "
            "RESEARCHED 2026-09-20. Retired from HF's Open LLM Leaderboard in June "
            "2024 with the rest of the v1 set — which is why saturation_flagged is "
            "True; it read False until a backtest test noticed the contradiction "
            "with these notes. Note it measures imitation of common "
            "human misconceptions, not factual accuracy in general — the category "
            "label here is a stretch. "
            "SATURATION IS MEASURED — corrected 2026-09-23, owner-authorized. "
            "This read: 'CURATE(you): no Epoch score file, so saturation is "
            "unmeasured'. There is no Epoch file, but there is an HF Open LLM "
            "Leaderboard v1 one: saturation is 0.375 over 7,170 rows "
            "(data/benchmark_scores/truthfulqa__open_llm_leaderboard_v1.csv) and "
            "the discrimination factor carries basis='measured'. THE READING IS "
            "FROZEN, which is the caveat that matters: v1 was ARCHIVED in June 2024 "
            "along with this benchmark, so no model has been added since and this "
            "number cannot move however saturated TruthfulQA becomes. It measures "
            "the 2024 population, not today's. That is the open "
            "submission-pipeline defect, and it is why a frozen reading must not be "
            "read as evidence the benchmark still discriminates. FURTHER CAVEAT "
            "2026-09-23: 358 of those 7,170 rows are the same model at a second "
            "precision, so the distinct-model population is 6,812 — "
            "docs/CONFIG_ROWS.md. STILL OPEN and untouched by this correction: "
            "decide whether this belongs under 'factual accuracy' at all, since it "
            "measures imitation of common human misconceptions."
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
        specificity_dimensions=(2, 0, 1, 0, 0),
                evidence_dates={
            "saturation_flagged": "2024-06-26",  # HF retirement
        },
        curation_notes=(
            "SPECIFICITY: Rubric v2, applied by Claude Code 2026-09-21, adopted by owner 2026-09-21. Not independently checked: a second reviewer scoring a sample would be the validation. "
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
        specificity_dimensions=(2, 2, 2, 1, 2),
        holdout="partial_holdout",  # ~34% of tests held out
        curation_notes=(
            "SPECIFICITY: Rubric v2, applied by Claude Code 2026-09-21, adopted by owner 2026-09-21. Not independently checked: a second reviewer scoring a sample would be the validation. "
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
        specificity_dimensions=(1, 2, 2, 1, 1),
        curation_notes=(
            "SPECIFICITY: Rubric v2, applied by Claude Code 2026-09-21, adopted by owner 2026-09-21. Not independently checked: a second reviewer scoring a sample would be the validation. "
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
        specificity_dimensions=(1, 2, 2, 2, 2),
        curation_notes=(
            "SPECIFICITY: Rubric v2, applied by Claude Code 2026-09-21, adopted by owner 2026-09-21. Not independently checked: a second reviewer scoring a sample would be the validation. "
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
        specificity_dimensions=(2, 2, 2, 2, 2),
        curation_notes=(
            "SPECIFICITY: Rubric v2, applied by Claude Code 2026-09-21, adopted by owner 2026-09-21. Not independently checked: a second reviewer scoring a sample would be the validation. "
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
        specificity_dimensions=(1, 2, 2, 2, 2),
        holdout="partial_holdout",  # reference solutions never published upstream
        curation_notes=(
            "SPECIFICITY: Rubric v2, applied by Claude Code 2026-09-21, adopted by owner 2026-09-21. Not independently checked: a second reviewer scoring a sample would be the validation. "
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
        specificity_dimensions=(2, 2, 2, 2, 2),
        holdout="partial_holdout",  # held-out tests + unpublished maintainer rubric
        curation_notes=(
            "SPECIFICITY: Rubric v2, applied by Claude Code 2026-09-21, adopted by owner 2026-09-21. Not independently checked: a second reviewer scoring a sample would be the validation. "
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
        key="winogrande",
        name="Winogrande",
        category="commonsense reasoning",
        # "Winogrande XL (xl)" appears in model cards: "xl" is the standard
        # config name for the 40k-example training size, and the benchmark
        # is identical. Verified 2026-09-22. NOT aliased: XWinograd, which
        # is a different multilingual Winograd-schema set.
        aliases=(
            "WinoGrande", "wino_grande_external", "winogrande_xl",
            "Winogrande XL (xl)", "Winogrande XL",
        ),
        release_date="2019-07-24",
        dataset_size=44000,
        contamination_flagged=True,
        saturation_flagged=True,
        independent_evaluators=4,
        specificity_dimensions=(1, 0, 1, 0, 0),
        evidence_dates={
            "saturation_flagged": "2024-06-26",  # HF retirement announcement
            # CURATE(you): contamination is assumed from 2019 public release,
            # with no dated study quantifying it, so as-of scoring ignores it.
        },
        curation_notes=(
            "SPECIFICITY: Rubric v2, applied by Claude Code 2026-09-21, adopted by owner 2026-09-21. Not independently checked: a second reviewer scoring a sample would be the validation. "
            "RESEARCHED 2026-09-21. Sakaguchi et al., arXiv 1907.10641 (2019-07-24), "
            "AI2: 44k fill-in-the-blank pronoun-resolution problems, built by "
            "crowdsourcing plus AFLITE adversarial debiasing to make the original "
            "Winograd Schema Challenge harder and larger. Retired from HF's Open LLM "
            "Leaderboard in June 2024 with the rest of the v1 set, for saturation — "
            "which is why it is catalogued: it is one of the six benchmarks the "
            "backtest checks against. https://arxiv.org/abs/1907.10641 "
            "CURATE(you): contamination_flagged is set on the 2019 public release "
            "and the AFLITE construction being widely reproduced, NOT on a study "
            "that counted overlap. No rate, no effect, no evidence date — so it is "
            "invisible to as-of scoring, which is the correct treatment for a claim "
            "that cannot be dated. Finding a real decontamination study would be "
            "worth more than the flag. "
            "CURATE(you): EVALUATORS=4 IS PARTLY UNSOURCED. Three are verifiable "
            "and hold score files in this repo or published the benchmark: AI2 "
            "(the authors), HF's Open LLM Leaderboard v1, and Epoch AI. The fourth "
            "is not identified — the count was assigned by Claude Code 2026-09-21 "
            "on the general observation that Winogrande is widely reported, which "
            "is not the same as four independent evaluators. Either name a fourth "
            "or drop it to 3. "
            "WHERE THIS COUNT IS ACTUALLY USED: nowhere, when scoring today. Since "
            "this repo pulled Winogrande scores from two comparable sources, "
            "reproducibility is MEASURED (2.1 points of scatter -> 0.741) and the "
            "curated count is ignored. But cross-source agreement is unavailable "
            "under as-of scoring, so the count IS what the 2024-06-01 backtest "
            "uses — 4/5 = 0.8 there versus 0.741 measured. The unsourced number is "
            "live in the one test the project has, and dead in normal use."
        ),
        epoch_source_file="wino_grande_external.csv",
    ),
    Benchmark(
        key="gsm8k",
        name="GSM8K",
        category="mathematical reasoning",
        aliases=("GSM-8K", "gsm8k_external", "grade school math"),
        release_date="2021-10-27",
        dataset_size=8500,
        contamination_flagged=True,
        item_error_rate=0.02,  # creators' own quality-control estimate
        # MEAN relative drop across the 63 models in GSM1k's Appendix F
        # table, computed by probes/gsm1k_effect.py. NOT the published
        # "up to 8%", which is a maximum. See the notes for why this is
        # only partly comparable to HumanEval's 0.394.
        contamination_effect=0.051,
        # GSM1k was built to match GSM8K's difficulty distribution —
        # human solve rates, solution steps, answer magnitude — so this
        # is close to a pure contamination measurement.
        contamination_effect_basis="difficulty_controlled",
        saturation_flagged=True,
        independent_evaluators=5,
        specificity_dimensions=(1, 1, 1, 0, 1),
        evidence_dates={
            "saturation_flagged": "2024-06-26",  # HF retirement announcement
            "contamination_flagged": "2024-05-01",  # GSM1k, arXiv 2405.00332
            # Same paper, same date. PREDATES the 2024-06-01 backtest
            # cutoff, so unlike most evidence here it IS visible to the
            # backtest and does move it.
            "contamination_effect": "2024-05-01",
            "item_error_rate": "2021-10-27",  # stated in the original paper
        },
        curation_notes=(
            "SPECIFICITY: Rubric v2, applied by Claude Code 2026-09-21, adopted by owner 2026-09-21. Not independently checked: a second reviewer scoring a sample would be the validation. "
            "RESEARCHED 2026-09-21. Cobbe et al. (2021-10-27, arXiv 2110.14168): "
            "8.5K grade-school word problems taking 2-8 elementary arithmetic steps, "
            "with natural-language solutions. Retired from HF's Open LLM Leaderboard "
            "in June 2024 with the rest of the v1 set. "
            "CONTAMINATION — QUANTIFIED 2026-09-21, resolving the CURATE marker "
            "that asked for a mean instead of the published maximum. Scale AI "
            "commissioned GSM1k, 1,205 problems written by human annotators to "
            "mirror GSM8K's style AND its difficulty distribution (human solve "
            "rates, solution steps, answer magnitude), so the comparison isolates "
            "memorization rather than difficulty. Phi and Mistral families show "
            "systematic overfitting across sizes; frontier models show little. A "
            "model\'s probability of generating a GSM8K example correlates with "
            "its GSM8K-to-GSM1k gap (Spearman r^2 = 0.36). "
            "https://arxiv.org/abs/2405.00332 (v4, NeurIPS 2024 D&B) "
            "HOW 0.051 WAS COMPUTED: from the per-model table in Appendix F of "
            "the paper itself (63 models, standard LM-Eval-Harness prompt), "
            "extracted by probes/gsm1k_effect.py. For each model, relative drop = "
            "(GSM8K - GSM1k) / GSM8K; contamination_effect is the MEAN of those. "
            "Mean 0.051, median 0.044, mean absolute drop 2.1 points, max absolute "
            "drop 8.0 points — the last reproduces the paper\'s headline \'up to "
            "8%\', which is how the parse was validated. Excluding the two models "
            "scoring under 10% on GSM8K (gpt2-xl, pythia-12b, whose tiny "
            "denominators inflate a ratio) gives 0.044; no filter was applied, "
            "because any threshold would be a choice nobody can source. "
            "CORRECTION: the previous note said \'up to 13%\' and r^2 = 0.32. "
            "Those are v1 figures. The published v4 says 8% and 0.36. "
            "CURATE(you) — THE DEFINITION IS NOT FULLY COMPARABLE TO HUMANEVAL\'S "
            "0.394, and the field cannot express the difference. The arithmetic "
            "matches (mean relative drop across a broad model set: 63 here, 51 "
            "there) but the control sets do not. GSM1k holds difficulty constant "
            "by construction, so its 5.1% is close to pure contamination. "
            "HumanEval\'s 0.394 comes from EvoEval, whose problems are LLM-evolved "
            "transformations of the originals with no difficulty control, so that "
            "figure mixes contamination with the transformed problems simply being "
            "harder. Two numbers in one field measuring different things is the "
            "same class of error the original CURATE marker here was written to "
            "avoid — one level up. Recorded rather than hidden: the honest fix is "
            "a separate field, or an EvoEval-equivalent for GSM8K, not a fudge. "
            "ITEM QUALITY: 0.02 is the creators' own estimate from their quality "
            "control, the same kind of self-reported figure that turned out to be "
            "far too low for SWE-Bench Verified. Treat it as a floor of a different "
            "sort: nobody independent has audited GSM8K's labels. "
            "CURATE(you): dataset_size records the 8.5K headline. The paper "
            "describes a 7.5K/1K train/test split while the released test split is "
            "1,319 problems; the discrepancy is unresolved and matters if anyone "
            "computes per-item error bars. "
            "CURATE(you): EVALUATORS=5 IS PARTLY UNSOURCED. Three are verifiable: "
            "OpenAI (the authors), HF's Open LLM Leaderboard v1, and Epoch AI — "
            "the latter two hold score files in this repo. Scale AI's GSM1k study "
            "is arguably a fourth, though it evaluated a fresh set rather than "
            "GSM8K itself. The fifth is not identified; the count was assigned by "
            "Claude Code 2026-09-21 on GSM8K's ubiquity, and a lab quoting its own "
            "GSM8K number in a model card is not an independent evaluator. "
            "WHERE THIS COUNT IS ACTUALLY USED, AND WHY IT IS THE WORST CASE IN "
            "THE CATALOG: not at all when scoring today — two comparable sources "
            "exist, so reproducibility is MEASURED, and the measurement is dire "
            "(6.9 points of scatter plus a systematic 7.0-point harness gap -> "
            "0.134). But as-of scoring cannot use cross-source agreement, so the "
            "2024-06-01 backtest falls back to the count: 5/5 = FULL CREDIT, 1.0. "
            "A retired, saturated benchmark whose published scores demonstrably "
            "cannot be reproduced across harnesses is handed a perfect "
            "reproducibility score in the only test this project runs, on the "
            "strength of an unsourced count. That is the largest single gap "
            "between what the scorer knows today and what it is allowed to know "
            "at the cutoff, and it pushes in the direction of making the backtest "
            "HARDER to pass, not easier."
        ),
        epoch_source_file="gsm8k_external.csv",
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
        specificity_dimensions=(2, 1, 1, 0, 1),
                evidence_dates={
            "saturation_flagged": "2026-09-20",  # this repo's measurement
            # CURATE(you): Epoch's contamination warning carries no date I
            # could pin, so it is excluded from as-of scoring.
        },
        curation_notes=(
            "SPECIFICITY: Rubric v2, applied by Claude Code 2026-09-21, adopted by owner 2026-09-21. Not independently checked: a second reviewer scoring a sample would be the validation. "
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
        key="musr",
        name="MuSR",
        category="commonsense reasoning",
        aliases=("MUSR", "Multistep Soft Reasoning", "musr"),
        release_date="2023-10-24",
        # MEASURED 2026-09-21 by counting the released CSVs, not from the
        # paper: 250 murder mysteries + 256 object placements + 250 team
        # allocations = 756, which also matches all.csv exactly. The widely
        # repeated 756 is correct. See probes/musr_baseline.py.
        dataset_size=756,
        contamination_flagged=False,
        saturation_flagged=False,
        independent_evaluators=2,
        specificity_dimensions=(0, 0, 1, 0, 1),
        evidence_dates={},
        curation_notes=(
            "SPECIFICITY: Rubric v2, applied by Claude Code 2026-09-21, adopted by owner 2026-09-21. Not independently checked: a second reviewer scoring a sample would be the validation. "
            "RESEARCHED 2026-09-21. Sprague et al., arXiv 2310.16049 (2023-10-24), "
            "ICLR 2024: narrative reasoning problems generated by a neurosymbolic "
            "synthetic-to-natural pipeline, spanning murder mysteries (~1000 words "
            "each), object placement and team allocation. Chosen for HF's Open LLM "
            "Leaderboard v2 in June 2024 as one of the harder replacements, which is "
            "why it is catalogued — it is one of the six the backtest checks. "
            "https://arxiv.org/abs/2310.16049 "
            "DATASET SIZE AND RANDOM BASELINE — MEASURED 2026-09-21 by probing "
            "TAUR-Lab/MuSR directly (probes/musr_baseline.py), replacing two "
            "earlier CURATE markers. 756 items confirmed: 250 murder mysteries + "
            "256 object placements + 250 team allocations, matching all.csv. "
            "THE BASELINE WAS WRONG, and wrong in MuSR's favour. It was recorded "
            "as 0.33 on the assumption of three options throughout. Counting "
            "options per item shows the murder-mystery split is BINARY (chance "
            "0.5), object placement varies from 2 to 5 options (chance 0.282) and "
            "only team allocation is genuinely three-way (0.333). The aggregate "
            "is 0.371, and the item-weighted and subtask-weighted aggregations "
            "agree to 0.0007 because the three subtasks are nearly the same size, "
            "so the number does not hinge on how the leaderboard aggregates. "
            "HF's own v2 rescaling, inverted out of their raw and normalized "
            "columns, implies ~0.345 — but it varies per model, which shows they "
            "normalized each subtask separately rather than using one aggregate "
            "baseline. Their number is not directly comparable; it does confirm "
            "0.33 was too low. Derivation in fetch_benchmark_scores.RANDOM_BASELINES. "
            "CONSEQUENCE, measured rather than predicted — and the opposite of "
            "what was first written here: saturation FALLS 0.474 -> 0.440 and "
            "trust RISES 42.3 -> 43.7. Both saturation terms are fractions of "
            "(ceiling - baseline), so raising the baseline shrinks the "
            "denominator: the leaders near 0.57 become a smaller share of what is "
            "left (less headroom used) while the same absolute gap becomes a "
            "wider relative spread. See the derivation comment in "
            "fetch_benchmark_scores for why the spread half of that is a "
            "rescaling artifact. The value was committed from the dataset before "
            "its direction was known. "
            "CURATE(you): no contamination or item-quality study found. That is "
            "absence of evidence — the generation pipeline is public, so a "
            "regenerated variant would be a cheap contamination check."
        ),
        epoch_source_file=None,
    ),
    Benchmark(
        key="ifeval",
        name="IFEval",
        category="instruction following",
        aliases=("IFEval Raw", "Instruction-Following Eval", "ifeval"),
        release_date="2023-11-14",
        dataset_size=541,
        contamination_flagged=False,
        saturation_flagged=False,
        independent_evaluators=2,
        specificity_dimensions=(1, 2, 2, 1, 0),
        evidence_dates={},
        curation_notes=(
            "SPECIFICITY: Rubric v2, applied by Claude Code 2026-09-21, adopted by owner 2026-09-21. Not independently checked: a second reviewer scoring a sample would be the validation. "
            "RESEARCHED 2026-09-21. Zhou et al., arXiv 2311.07911 (2023-11), Google: "
            "541 prompts carrying 25 types of VERIFIABLE instruction — 'write more "
            "than 400 words', 'mention the keyword AI at least 3 times' — each "
            "checkable by a deterministic program rather than a human or an LLM "
            "judge. Chosen for HF's Open LLM Leaderboard v2 in June 2024. "
            "https://arxiv.org/abs/2311.07911 "
            "New category 'instruction following' added for it; none of the existing "
            "nine fitted without distorting the label. "
            "CURATE(you): no contamination or item-quality study found, and the "
            "prompts are public since 2023. Absence of evidence, not evidence of "
            "absence. "
            "CURATE(you): evaluator count of 2 (the authors, HF's leaderboard) is a "
            "floor — IFEval appears in many model cards, but a lab self-reporting "
            "its own score is not an independent evaluator."
        ),
        epoch_source_file=None,
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
        specificity_dimensions=(1, 1, 0, 0, 0),
        curation_notes=(
            "SPECIFICITY: Rubric v2, applied by Claude Code 2026-09-21, adopted by owner 2026-09-21. Not independently checked: a second reviewer scoring a sample would be the validation. "
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
        specificity_dimensions=(1, 1, 1, 0, 0),
        curation_notes=(
            "SPECIFICITY: Rubric v2, applied by Claude Code 2026-09-21, adopted by owner 2026-09-21. Not independently checked: a second reviewer scoring a sample would be the validation. "
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
        specificity_dimensions=(1, 2, 2, 2, 2),
        curation_notes=(
            "SPECIFICITY: Rubric v2, applied by Claude Code 2026-09-21, adopted by owner 2026-09-21. Not independently checked: a second reviewer scoring a sample would be the validation. "
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
        specificity_dimensions=(1, 2, 2, 2, 2),
        curation_notes=(
            "SPECIFICITY: Rubric v2, applied by Claude Code 2026-09-21, adopted by owner 2026-09-21. Not independently checked: a second reviewer scoring a sample would be the validation. "
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
        key="mbpp",
        name="MBPP",
        category="code generation",
        aliases=("Mostly Basic Programming Problems", "mbpp", "MBPP (sanitized)"),
        release_date="2021-08-16",
        # The 500-problem TEST split, not the 974-problem total. Model
        # cards almost always report the test split, and recording the
        # total would overstate what a score is computed over.
        dataset_size=500,
        contamination_flagged=True,
        saturation_flagged=False,
        independent_evaluators=3,
        specificity_dimensions=(1, 2, 2, 1, 0),
        evidence_dates={
            # CURATE(you): contamination is asserted from the 2021 public
            # release and MBPP's ubiquity in code pretraining corpora, NOT
            # from a study that counted overlap. Undated on purpose, so
            # as-of scoring ignores it.
        },
        curation_notes=(
            "SPECIFICITY: Rubric v2, applied by Claude Code 2026-09-22, adopted by "
            "owner 2026-09-21. Not independently checked: a second reviewer scoring "
            "a sample would be the validation. Dimensions (1,2,2,1,0): problems "
            "written by humans for the benchmark, not drawn from real work (A1); "
            "the model produces a Python function verified by executing three "
            "assert statements (B2); one identifiable task type, implementing a "
            "short function from a description (C2); writing small functions is a "
            "component of programming work (D1); single short function, one shot "
            "(E0). "
            "RESEARCHED 2026-09-22. Austin et al., arXiv 2108.07732 (2021-08-16), "
            "Google: 974 crowd-sourced Python problems 'solvable by entry-level "
            "programmers', each with one reference solution averaging 6.8 lines and "
            "THREE assert-statement unit tests. Split 374 train / 90 validation / "
            "500 test / 10 few-shot. https://arxiv.org/abs/2108.07732 "
            "WHY IT IS CATALOGUED: it is the second-most-standard code benchmark "
            "after HumanEval and the most defensible addition from the model side's "
            "citation list. It is cited by ONE model in this repo's catalog, which "
            "is the point of the coverage finding rather than an argument against "
            "adding it — see docs/MODEL_SIDE_AUDIT.md. "
            "CURATE(you): NO SCORE DATA. Neither Epoch's export nor the HF "
            "leaderboards carry MBPP, so saturation is UNMEASURABLE and this entry "
            "sits in the THIN evidence tier — its health rests on freshness alone. "
            "EvalPlus publishes MBPP+ and would be the obvious source; it publishes "
            "no model dates, which is why HumanEval's EvalPlus set is also "
            "date-less here. "
            "CURATE(you): contamination_flagged is set on the 2021 public release "
            "and MBPP's presence in every major code corpus, NOT on a study that "
            "counted overlap. No rate, no effect, no evidence date — so it is "
            "invisible to as-of scoring and, since 2026-09-21, carries no numeric "
            "penalty either. Riddell et al. (arXiv 2403.04811) DID measure MBPP "
            "overlap — 3.6% to 20.8% of solutions seen, with relative accuracy "
            "degradations of 4.5% to 28.6% depending on threshold — and those "
            "figures are deliberately NOT recorded here, because they are drawn "
            "from three small pre-2024 models (StarCoderBase, Pythia, CodeGen-NL) "
            "and this catalog's other contamination rates come from corpus-wide "
            "overlap studies. Recording them would repeat the max-vs-mean and "
            "controlled-vs-uncontrolled errors this project has already made "
            "twice. "
            "CURATE(you): item quality unaudited. MBPP's tests are three asserts "
            "per problem, which is thinner than HumanEval's, and the sanitized "
            "subset (427 problems) exists precisely because the original had "
            "quality issues — a strong hint that item_error_rate is not zero, and "
            "not a number."
        ),
        epoch_source_file=None,
    ),
    Benchmark(
        key="ds_1000",
        name="DS-1000",
        category="code generation",
        aliases=("DS1000", "ds-1000", "DS-1000 (Completion)"),
        release_date="2022-11-18",
        dataset_size=1000,
        contamination_flagged=False,
        saturation_flagged=False,
        independent_evaluators=2,
        specificity_dimensions=(2, 2, 2, 1, 0),
        evidence_dates={},
        curation_notes=(
            "SPECIFICITY: Rubric v2, applied by Claude Code 2026-09-22, adopted by "
            "owner 2026-09-21. Not independently checked: a second reviewer scoring "
            "a sample would be the validation. Dimensions (2,2,2,1,0): problems "
            "collected from real StackOverflow questions, i.e. artifacts that "
            "existed because someone had the problem (A2); the model writes code "
            "verified by execution AND surface-form checks on API usage (B2); one "
            "identifiable task type, data-science code completion (C2); a "
            "recognisable component of analysis work rather than a whole "
            "deliverable (D1); single completion, one shot (E0). "
            "RESEARCHED 2026-09-22. Lai et al., arXiv 2211.11501 (2022-11-18), "
            "ICML 2023: 1,000 data-science problems across seven libraries (NumPy, "
            "Pandas, TensorFlow, PyTorch, SciPy, scikit-learn, Matplotlib), "
            "collected from StackOverflow. https://arxiv.org/abs/2211.11501 "
            "WHY IT IS CATALOGUED, and it is the interesting one: DS-1000 "
            "PROACTIVELY DEFENDS AGAINST MEMORIZATION by perturbing each problem "
            "away from its StackOverflow original, so a model cannot answer by "
            "recalling the source. That is the difficulty-controlled design this "
            "catalog has been looking for and could not find for HumanEval — see "
            "HumanEval's CURATE note on EvoEval. It is the strongest leakage "
            "defence of any code benchmark here that is not held out. "
            "The authors also report that of all accepted Codex-002 solutions only "
            "1.8% were actually incorrect, which is an unusually direct "
            "false-acceptance measurement and the opposite of the SWE-Bench "
            "problem. "
            "CURATE(you): HOLDOUT NOT RECORDED AS A DEFENCE. The perturbation is a "
            "construction-time defence, not a withheld answer key, so holdout "
            "stays 'public_static'. Whether this repo's holdout taxonomy should "
            "have a 'perturbed' value is an open question — it is a real leakage "
            "defence that the four current values cannot express. "
            "CURATE(you): the 1.8% false-acceptance figure is NOT recorded as an "
            "item_error_rate. It measures the opposite quantity (tests that accept "
            "a wrong answer, rather than reject a right one) on a single 2022 "
            "model. Putting it in that field would be the one-field-two-quantities "
            "violation named in CLAUDE.md section 3. "
            "CURATE(you): NO SCORE DATA in Epoch or the HF leaderboards, so "
            "saturation is unmeasurable and this entry is THIN tier."
        ),
        epoch_source_file=None,
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
        specificity_dimensions=(2, 1, 1, 0, 0),
                evidence_dates={
            # CURATE(you): contamination here is assumed from the 2017 web
            # provenance, with no dated study, so as-of scoring ignores it.
        },
        curation_notes=(
            "SPECIFICITY: Rubric v2, applied by Claude Code 2026-09-21, adopted by owner 2026-09-21. Not independently checked: a second reviewer scoring a sample would be the validation. "
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
    def population(self) -> str:
        """
        WHICH MODELS this distribution covers, in words.

        Derived from `source` via SOURCE_POPULATIONS — no new data, just
        the provenance the manifest already records, surfaced where a
        reader can see it. A saturation number means nothing without it:
        GPQA Diamond reads 0.894 among frontier models and 0.588 among
        the open community, and those are answers to different questions
        rather than a disagreement to be averaged away.
        """
        return describe_population(self.source)

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
