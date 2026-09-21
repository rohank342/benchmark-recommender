"""
task_matcher.py
===============
Maps a user's description of their work onto benchmark categories, then
hands back the benchmarks for that category ranked by trust rather than
by fame.

This is the join between "what am I actually doing" and "which
measurement means anything for it". Someone building a coding agent is
usually pointed at HumanEval because it is the famous one; what they
want is the benchmark that still discriminates on work resembling
theirs.

Matching is keyword-based and deliberately transparent — it reports the
terms it matched on, so a wrong category is visible rather than
mysterious. A learned classifier would match more phrasings, but this
has to be auditable before it is clever.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from benchmark_scoring import BenchmarkTrust, score_all_benchmarks
from fetch_benchmarks import CATEGORIES

########################################################################
# CURATE(you): the vocabulary each category answers to. Add phrasings as
# you see real queries miss — every term here is a judgement about what
# people mean, and it's cheap to extend.
########################################################################
CATEGORY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "code generation": (
        "code", "coding", "codegen", "code generation", "write code", "programming",
        "program", "function", "script", "autocomplete", "completion", "snippet",
        "python", "javascript", "typescript", "rust", "java", "sql",
    ),
    "software engineering": (
        "software engineering", "swe", "bug", "bugfix", "fix bugs", "debug",
        "refactor", "pull request", "github issue", "issue", "repository", "repo",
        "codebase", "patch", "maintenance", "legacy code",
    ),
    "agentic tool use": (
        "agent", "agentic", "tool use", "tool calling", "function calling",
        "workflow", "automation", "multi-step", "planning", "orchestration",
        "terminal", "shell", "command line", "cli",
    ),
    "computer use": (
        "computer use", "gui", "desktop", "browser", "click", "screen",
        "screenshot", "operate", "ui automation", "web navigation",
    ),
    "general knowledge": (
        "general knowledge", "trivia", "facts", "encyclopedia", "broad knowledge",
        "world knowledge", "exam", "quiz", "multiple choice",
    ),
    "scientific reasoning": (
        "science", "scientific", "physics", "chemistry", "biology", "research",
        "phd", "medical", "medicine", "clinical", "diagnosis", "scientific reasoning",
    ),
    "mathematical reasoning": (
        "math", "maths", "mathematics", "arithmetic", "algebra", "calculus",
        "proof", "theorem", "quantitative", "numerical",
    ),
    "commonsense reasoning": (
        "commonsense", "common sense", "reasoning", "inference", "logic",
        "everyday", "narrative", "reading comprehension",
    ),
    "instruction following": (
        "instruction following", "follow instructions", "formatting", "format",
        "constraint", "constraints", "output format", "json output", "structured output", "style guide", "word count", "obey", "compliance",
    ),
    "factual accuracy": (
        "factual", "factuality", "hallucination", "truthful", "accuracy",
        "citation", "grounding", "verification", "fact check",
    ),
}


@dataclass
class TaskMatch:
    """What the matcher concluded, and why."""

    category: Optional[str]
    confidence: float  # 0-1
    matched_terms: list[str] = field(default_factory=list)
    alternatives: list[tuple[str, float]] = field(default_factory=list)

    @property
    def explanation(self) -> str:
        if self.category is None:
            return (
                "No category matched that description. Pick one directly, or add "
                "the phrasing to CATEGORY_KEYWORDS in task_matcher.py."
            )
        terms = ", ".join(f"'{t}'" for t in self.matched_terms[:4])
        line = f"Matched **{self.category}** on {terms}."
        if self.alternatives:
            others = ", ".join(f"{name} ({score:.0%})" for name, score in self.alternatives[:2])
            line += f" Runners-up: {others}."
        return line


def _terms_in(description: str, keywords: tuple[str, ...]) -> list[str]:
    text = description.lower()
    found = []
    for keyword in keywords:
        # Word-boundary match so "sql" doesn't fire inside "mysqld" and
        # "agent" doesn't fire inside "urgent".
        if re.search(rf"\b{re.escape(keyword)}\b", text):
            found.append(keyword)
    return found


def match_task(description: str) -> TaskMatch:
    """
    Map a free-text task description to a benchmark category.

    Longer matched phrases outweigh single words, so "agentic tool use"
    beats an incidental "code" elsewhere in the sentence.
    """
    if not description or not description.strip():
        return TaskMatch(category=None, confidence=0.0)

    scores: dict[str, float] = {}
    matches: dict[str, list[str]] = {}
    for category, keywords in CATEGORY_KEYWORDS.items():
        found = _terms_in(description, keywords)
        if not found:
            continue
        # Weight by phrase length: a two-word phrase is stronger evidence
        # than a single generic word.
        weight = sum(1.0 + 0.5 * (len(term.split()) - 1) for term in found)
        scores[category] = weight
        matches[category] = sorted(found, key=len, reverse=True)

    if not scores:
        return TaskMatch(category=None, confidence=0.0)

    total = sum(scores.values())
    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    best_category, best_score = ranked[0]
    return TaskMatch(
        category=best_category,
        confidence=round(best_score / total, 3),
        matched_terms=matches[best_category],
        alternatives=[(name, score / total) for name, score in ranked[1:]],
    )


def benchmarks_for_category(
    category: Optional[str], scored: Optional[list[BenchmarkTrust]] = None
) -> list[BenchmarkTrust]:
    """Trust-ranked benchmarks for one category."""
    scored = scored if scored is not None else score_all_benchmarks()
    if category is None:
        return scored
    return [t for t in scored if t.benchmark.category == category]


def recommend_benchmarks(
    description: str, scored: Optional[list[BenchmarkTrust]] = None
) -> tuple[TaskMatch, list[BenchmarkTrust]]:
    """
    The main entry point: description in, (what we matched, ranked
    benchmarks) out. An unmatched description returns the whole catalog
    rather than nothing — the user can still see the landscape.
    """
    match = match_task(description)
    return match, benchmarks_for_category(match.category, scored)


def all_categories() -> tuple[str, ...]:
    return CATEGORIES


if __name__ == "__main__":
    for description in (
        "code generation",
        "I'm building an agent that uses tools and runs shell commands",
        "medical QA for clinicians",
        "fixing bugs in a large legacy repository",
        "underwater basket weaving",
    ):
        match, benchmarks = recommend_benchmarks(description)
        print(f"\n{description!r}")
        print(f"  {match.explanation}")
        for trust in benchmarks[:3]:
            print(f"    {trust.trust_score:>5.1f}  {trust.benchmark.name}")
