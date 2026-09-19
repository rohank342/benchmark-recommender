"""
hardware_filter.py
===================
Estimates how much VRAM a model needs and filters by GPU budget.

Memory splits into three parts:

  weights  = params x bytes-per-param at the chosen precision
  KV cache = 2 (K and V) x layers x kv_heads x head_dim x context x 2 bytes
  workspace = activations, buffers, fragmentation

The KV cache is the part the first version of this file ignored, and it
is the part that decides whether a model fits: it grows linearly with
context length, and at long context it can exceed the weights themselves.
A 7B model at 4K and the same model at 128K are different memory
questions, so `context_tokens` is an input everywhere.

Quantization is read from the repo rather than assumed. A repo that ships
AWQ 4-bit weights cannot be run at fp16, and offering that is a
recommendation the user cannot act on.

########################################################################
# TODO(you): the numbers here are derived, not measured. Real usage also
# depends on the serving stack (vLLM's paged attention, llama.cpp's
# layer offloading), batch size, and whether the KV cache itself is
# quantized. Measure a few models per quant level and fit from that.
########################################################################
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

# Bytes per parameter at each precision the user can choose.
BYTES_PER_PARAM = {"fp16": 2.0, "8bit": 1.0, "4bit": 0.5}
PRECISIONS_HIGH_TO_LOW = ("fp16", "8bit", "4bit")

# The KV cache holds one key and one value vector per layer per token,
# in fp16 unless the serving stack quantizes it too.
KV_BYTES_PER_ELEMENT = 2.0

# Activations, CUDA context, allocator fragmentation. Roughly constant
# next to weights and cache, and deliberately generous: an estimate that
# says "fits" for a model that then OOMs is the expensive kind of wrong.
WORKSPACE_GB = 1.0

# Used only when config.json is unavailable (GGUF repos, mostly) and the
# KV cache can't be computed from real dimensions.
FALLBACK_KV_GB_PER_BILLION_PARAMS = 0.12

GB = 1024**3


@dataclass
class VramEstimate:
    """Everything needed to explain a fit decision, not just the total."""

    precision: str
    weights_gb: Optional[float]
    kv_cache_gb: Optional[float]
    total_gb: Optional[float]
    kv_cache_estimated: bool  # True when dimensions were unavailable
    available: bool  # False when the repo can't run at this precision


def _architecture(model: dict[str, Any]) -> dict[str, Any]:
    arch = model.get("architecture")
    return arch if isinstance(arch, dict) else {}


def native_quant_bits(model: dict[str, Any]) -> Optional[int]:
    """Bit width the repo's weights already ship in, if it is quantized."""
    bits = _architecture(model).get("native_quant_bits")
    return bits if isinstance(bits, int) else None


def available_precisions(model: dict[str, Any]) -> tuple[str, ...]:
    """
    Precisions this repo can actually be run at.

    Weights that ship quantized can't be restored to a higher precision,
    so a 4-bit AWQ repo offers 4-bit only. Full-precision weights can be
    quantized at load time, so they offer all three.
    """
    bits = native_quant_bits(model)
    if bits is None:
        return PRECISIONS_HIGH_TO_LOW
    if bits <= 4:
        return ("4bit",)
    if bits <= 8:
        return ("8bit",)
    return PRECISIONS_HIGH_TO_LOW


def kv_cache_gb(model: dict[str, Any], context_tokens: int) -> tuple[Optional[float], bool]:
    """
    KV cache size at a given context length.

    Returns (gigabytes, estimated), where `estimated` is True when the
    repo's dimensions were unavailable and a per-parameter rule of thumb
    stood in for them.
    """
    arch = _architecture(model)
    layers = arch.get("num_hidden_layers")
    kv_heads = arch.get("num_key_value_heads")
    head_dim = arch.get("head_dim")

    if layers and kv_heads and head_dim:
        total_bytes = 2 * layers * kv_heads * head_dim * context_tokens * KV_BYTES_PER_ELEMENT
        return round(total_bytes / GB, 2), False

    params = model.get("params_billion")
    if params:
        # Scale the rule of thumb by context, anchored at 8K.
        scaled = FALLBACK_KV_GB_PER_BILLION_PARAMS * params * (context_tokens / 8192)
        return round(scaled, 2), True
    return None, True


def estimate_vram(
    model: dict[str, Any], precision: str, context_tokens: int = 8192
) -> VramEstimate:
    """Estimate VRAM for one model at one precision and context length."""
    params = model.get("params_billion")
    available = precision in available_precisions(model)

    if not params:
        return VramEstimate(precision, None, None, None, True, available)

    weights = params * BYTES_PER_PARAM[precision]
    cache, estimated = kv_cache_gb(model, context_tokens)
    total = weights + (cache or 0.0) + WORKSPACE_GB

    return VramEstimate(
        precision=precision,
        weights_gb=round(weights, 2),
        kv_cache_gb=cache,
        total_gb=round(total, 2),
        kv_cache_estimated=estimated,
        available=available,
    )


def best_fit_precision(
    model: dict[str, Any], available_vram_gb: float, context_tokens: int = 8192
) -> Optional[VramEstimate]:
    """
    Highest precision the model can actually be served at within budget,
    or None if it doesn't fit even at its lowest available precision.
    """
    for precision in PRECISIONS_HIGH_TO_LOW:
        if precision not in available_precisions(model):
            continue
        estimate = estimate_vram(model, precision, context_tokens)
        if estimate.total_gb is not None and estimate.total_gb <= available_vram_gb:
            return estimate
    return None


def max_context_supported(model: dict[str, Any]) -> Optional[int]:
    """The context length the model was trained/configured for, if known."""
    value = _architecture(model).get("max_position_embeddings")
    return value if isinstance(value, int) else None


def filter_models_by_vram(
    models: list[dict], available_vram_gb: float, context_tokens: int = 8192
) -> list[dict]:
    """
    Annotate each model with its VRAM estimate at `context_tokens` and
    keep those that fit.

    Models whose parameter count is unknown are kept and marked, rather
    than silently dropped: "we don't know" and "it doesn't fit" are
    different answers, and only one of them is the model's fault.
    """
    fitted = []
    for model in models:
        annotated = dict(model)
        precisions = available_precisions(model)
        estimate = best_fit_precision(model, available_vram_gb, context_tokens)

        if model.get("params_billion") is None:
            annotated.update(
                {
                    "best_fit_quant": None,
                    "vram_total_gb": None,
                    "vram_weights_gb": None,
                    "vram_kv_cache_gb": None,
                    "kv_cache_estimated": True,
                    "size_known": False,
                    "native_quant": native_quant_bits(model),
                    "max_context": max_context_supported(model),
                    "available_precisions": ", ".join(precisions),
                }
            )
            fitted.append(annotated)
            continue

        if estimate is None:
            continue

        annotated.update(
            {
                "best_fit_quant": estimate.precision,
                "vram_total_gb": estimate.total_gb,
                "vram_weights_gb": estimate.weights_gb,
                "vram_kv_cache_gb": estimate.kv_cache_gb,
                "kv_cache_estimated": estimate.kv_cache_estimated,
                "size_known": True,
                "native_quant": native_quant_bits(model),
                "max_context": max_context_supported(model),
                "available_precisions": ", ".join(precisions),
            }
        )
        fitted.append(annotated)
    return fitted


if __name__ == "__main__":
    # A 7B model with grouped-query attention, at two context lengths.
    qwen7b = {
        "params_billion": 7.62,
        "architecture": {
            "num_hidden_layers": 28,
            "num_key_value_heads": 4,
            "head_dim": 128,
            "max_position_embeddings": 32768,
        },
    }
    for context in (4096, 32768, 131072):
        estimate = estimate_vram(qwen7b, "fp16", context)
        print(
            f"{context:>7} tokens: {estimate.total_gb} GB "
            f"(weights {estimate.weights_gb}, kv {estimate.kv_cache_gb})"
        )

    awq = {"params_billion": 32.76, "architecture": {"native_quant_bits": 4}}
    print("\nAWQ 4-bit repo offers:", available_precisions(awq))
