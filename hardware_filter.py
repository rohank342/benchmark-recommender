"""
hardware_filter.py
===================
Rule-of-thumb VRAM estimation and filtering by GPU memory budget.

########################################################################
# TODO(you): these are back-of-envelope multipliers, not measured
# numbers. Real VRAM usage also depends on context length, KV-cache
# size, batch size, activation memory, and the specific quant method
# (GPTQ vs AWQ vs bitsandbytes vs GGUF all differ). Revisit once you
# want production-grade estimates — e.g. by measuring actual peak
# VRAM for a handful of models per quant level and fitting from that.
########################################################################
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

# Rule-of-thumb multipliers: estimated GB of VRAM per billion params.
# TODO(you): replace with measured/empirical multipliers when available.
VRAM_GB_PER_BILLION_PARAMS = {
    "fp16": 2.0,
    "8bit": 1.0,
    "4bit": 0.5,
}

# Extra headroom added on top of the raw weight size to account for
# activations/KV-cache at modest context lengths. Rough and configurable.
# TODO(you): make this context-length-aware instead of a flat overhead.
OVERHEAD_GB = 1.5


@dataclass
class VramEstimate:
    fp16_gb: Optional[float]
    bit8_gb: Optional[float]
    bit4_gb: Optional[float]


def estimate_vram(params_billion: Optional[float], include_overhead: bool = True) -> VramEstimate:
    """
    Estimate VRAM (in GB) needed to run a model at fp16, 8-bit, and
    4-bit quantization, given its parameter count in billions.
    """
    if params_billion is None:
        return VramEstimate(fp16_gb=None, bit8_gb=None, bit4_gb=None)

    overhead = OVERHEAD_GB if include_overhead else 0.0

    return VramEstimate(
        fp16_gb=round(params_billion * VRAM_GB_PER_BILLION_PARAMS["fp16"] + overhead, 2),
        bit8_gb=round(params_billion * VRAM_GB_PER_BILLION_PARAMS["8bit"] + overhead, 2),
        bit4_gb=round(params_billion * VRAM_GB_PER_BILLION_PARAMS["4bit"] + overhead, 2),
    )


def best_fit_quant(params_billion: Optional[float], available_vram_gb: float) -> Optional[str]:
    """
    Return the highest-precision quantization level ("fp16" > "8bit" >
    "4bit") that fits within available_vram_gb, or None if the model
    doesn't fit even at 4-bit.
    """
    estimate = estimate_vram(params_billion)
    if estimate.fp16_gb is not None and estimate.fp16_gb <= available_vram_gb:
        return "fp16"
    if estimate.bit8_gb is not None and estimate.bit8_gb <= available_vram_gb:
        return "8bit"
    if estimate.bit4_gb is not None and estimate.bit4_gb <= available_vram_gb:
        return "4bit"
    return None


def filter_models_by_vram(models: list[dict], available_vram_gb: float) -> list[dict]:
    """
    Given a list of model dicts (must include a "params_billion" key —
    e.g. ScoredModel.__dict__ entries), return only those that fit
    within available_vram_gb at some quantization level, annotated
    with their VRAM estimates and the best-fit quant level.
    """
    filtered = []
    for model in models:
        params = model.get("params_billion")
        estimate = estimate_vram(params)
        fit = best_fit_quant(params, available_vram_gb)
        if fit is None:
            continue
        annotated = dict(model)
        annotated["vram_fp16_gb"] = estimate.fp16_gb
        annotated["vram_8bit_gb"] = estimate.bit8_gb
        annotated["vram_4bit_gb"] = estimate.bit4_gb
        annotated["best_fit_quant"] = fit
        filtered.append(annotated)
    return filtered


if __name__ == "__main__":
    # Quick manual smoke test.
    print(estimate_vram(7.0))  # ~7B model
    print(best_fit_quant(7.0, available_vram_gb=8.0))
    print(best_fit_quant(70.0, available_vram_gb=8.0))
