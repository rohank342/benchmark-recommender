"""
model_matching.py
=================
Matching a Hugging Face repo id to the way an external source names the
same model is the hard part of enrichment. The Hub says
"Qwen/Qwen2.5-Coder-7B-Instruct"; Artificial Analysis says
"Qwen2.5 Coder 7B Instruct"; Epoch AI says something else again.

Strategy: reduce every name to a comparison key by lowercasing, dropping
the org prefix, dropping packaging/quantization markers, and removing
separators. Two names match only if their keys are *equal* — no fuzzy
matching. A false match silently attributes another model's benchmark
score, which is worse than no score at all.
"""

from __future__ import annotations

import re
from typing import Optional

# Markers that describe how weights are packaged or quantized, not which
# model they are. Stripping these lets a reupload like
# "bartowski/Qwen2.5-Coder-7B-Instruct-GGUF" match the original model.
FORMAT_MARKERS = frozenset(
    {
        "gguf",
        "ggml",
        "awq",
        "gptq",
        "exl2",
        "exl3",
        "mlx",
        "nvfp4",
        "fp4",
        "fp8",
        "fp16",
        "bf16",
        "int2",
        "int4",
        "int8",
        "bnb",
        "bitsandbytes",
        "quantized",
        "quant",
        "safetensors",
        "hf",  # e.g. codellama/CodeLlama-7b-hf
    }
)

# Quant level tokens: 4bit, 8-bit, w4a16, ...
_QUANT_TOKEN_RE = re.compile(r"^(\d+bit|w\d+a\d+)$")

# A trailing llama.cpp-style quant descriptor, which tokenizes into
# fragments that would otherwise survive: "-Q4_K_M", "-i1-Q5_K_S", "-q8_0".
_QUANT_SUFFIX_RE = re.compile(r"[-_.](i\d+[-_.])?q\d+([-_.][a-z0-9]+)*$", re.IGNORECASE)


def _tokens(name: str) -> list[str]:
    text = name.strip().lower()
    text = text.rsplit("/", 1)[-1]  # drop the org prefix
    text = re.sub(r"(?<=\d)\.(?=\d)", "", text)  # "2.5" -> "25"
    text = _QUANT_SUFFIX_RE.sub("", text)
    return [t for t in re.split(r"[^a-z0-9]+", text) if t]


def match_key(name: Optional[str]) -> Optional[str]:
    """
    Reduce a model name (Hub repo id or an external source's label) to a
    comparison key, or None if nothing identifying is left.
    """
    if not name:
        return None
    kept = [
        t
        for t in _tokens(name)
        if t not in FORMAT_MARKERS and not _QUANT_TOKEN_RE.match(t)
    ]
    return "".join(kept) or None


def key_from_huggingface_url(url: Optional[str]) -> Optional[str]:
    """
    Extract the repo id from a canonical Hub URL, as returned in
    Artificial Analysis' `huggingface_url` field (Pro tier), and reduce
    it to a match key.
    """
    if not url:
        return None
    match = re.search(r"huggingface\.co/([^/\s?#]+/[^/\s?#]+)", url)
    if not match:
        return None
    return match_key(match.group(1))


def repo_id_from_huggingface_url(url: Optional[str]) -> Optional[str]:
    """The exact `org/name` repo id in a Hub URL, for exact-id matching."""
    if not url:
        return None
    match = re.search(r"huggingface\.co/([^/\s?#]+/[^/\s?#]+)", url)
    return match.group(1) if match else None
