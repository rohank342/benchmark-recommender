"""
device_profiles.py
==================
What a given machine can actually run.

Memory is not the only constraint, and for many models it isn't the
binding one. A repo's weights are packaged for a particular runtime:
AWQ and GPTQ ship CUDA kernels, MLX is Apple-only, FP8 needs Ada or
newer, NVFP4 needs Blackwell. Recommending an AWQ repo to a MacBook is
not a rounding error — it's an answer the user cannot act on.

Load-time quantization is device-dependent too. On CUDA, a
full-precision repo can be loaded in 8- or 4-bit via bitsandbytes. On
Apple Silicon that path doesn't work, so a full-precision repo means
fp16 or nothing, and the practical route to a smaller footprint is a
GGUF or MLX build of the same weights.

Memory semantics differ as well: discrete VRAM is a hard wall, while
Apple's unified memory is shared with the OS (the GPU can claim roughly
70% by default) and degrades into swap rather than failing outright.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

# Artifact kinds, as reported by fetch_models' architecture parsing.
CUDA_QUANT_METHODS = frozenset(
    {"awq", "gptq", "bitsandbytes", "compressed-tensors", "modelopt", "gguf"}
)
APPLE_QUANT_METHODS = frozenset({"gguf", "mlx"})
CPU_QUANT_METHODS = frozenset({"gguf"})


@dataclass(frozen=True)
class DeviceProfile:
    key: str
    label: str
    memory_label: str
    # Fraction of the stated memory a model may actually claim.
    usable_memory_fraction: float
    # Pre-quantized artifact kinds this device can run.
    native_methods: frozenset
    # Whether full-precision weights can be quantized as they load.
    can_quantize_at_load: bool
    note: str


DEVICES: dict[str, DeviceProfile] = {
    "cuda_ampere": DeviceProfile(
        key="cuda_ampere",
        label="NVIDIA — Ampere or older (RTX 30xx, A100)",
        memory_label="GPU VRAM (GB)",
        usable_memory_fraction=0.95,
        native_methods=CUDA_QUANT_METHODS,
        can_quantize_at_load=True,
        note="FP8 and NVFP4 repos need newer hardware and are hidden.",
    ),
    "cuda_ada": DeviceProfile(
        key="cuda_ada",
        label="NVIDIA — Ada/Hopper (RTX 40xx, L40S, H100)",
        memory_label="GPU VRAM (GB)",
        usable_memory_fraction=0.95,
        native_methods=CUDA_QUANT_METHODS | {"fp8"},
        can_quantize_at_load=True,
        note="Runs FP8 natively; NVFP4 repos need Blackwell and are hidden.",
    ),
    "cuda_blackwell": DeviceProfile(
        key="cuda_blackwell",
        label="NVIDIA — Blackwell (RTX 50xx, B200)",
        memory_label="GPU VRAM (GB)",
        usable_memory_fraction=0.95,
        native_methods=CUDA_QUANT_METHODS | {"fp8", "nvfp4"},
        can_quantize_at_load=True,
        note="Runs every quantized format in this catalog.",
    ),
    "apple_silicon": DeviceProfile(
        key="apple_silicon",
        label="Apple Silicon (M-series, unified memory)",
        memory_label="Total unified memory (GB)",
        # macOS caps what the GPU may wire down at ~70% of system memory.
        usable_memory_fraction=0.70,
        native_methods=APPLE_QUANT_METHODS,
        can_quantize_at_load=False,
        note=(
            "bitsandbytes has no working MPS path, so full-precision repos run "
            "at fp16 only — use a GGUF or MLX build to go smaller. CUDA-only "
            "formats (AWQ, GPTQ, FP8, NVFP4) are hidden."
        ),
    ),
    "cpu": DeviceProfile(
        key="cpu",
        label="CPU only (no GPU)",
        memory_label="System RAM (GB)",
        usable_memory_fraction=0.80,
        native_methods=CPU_QUANT_METHODS,
        can_quantize_at_load=False,
        note="Workable via llama.cpp with GGUF, but expect a few tokens/second.",
    ),
}

DEFAULT_DEVICE = "cuda_ada"


def get_device(key: Optional[str]) -> DeviceProfile:
    return DEVICES.get(key or DEFAULT_DEVICE, DEVICES[DEFAULT_DEVICE])


def detect_local_device() -> str:
    """
    Best guess at the machine this is running on, used as the UI default.
    A guess only — people ask about hardware they aren't sitting at.
    """
    import platform

    system = platform.system()
    if system == "Darwin" and platform.machine() == "arm64":
        return "apple_silicon"
    try:
        import torch  # noqa: PLC0415  (optional dependency)

        if torch.cuda.is_available():
            major, _ = torch.cuda.get_device_capability()
            if major >= 10:
                return "cuda_blackwell"
            if major >= 9 or (major == 8 and torch.cuda.get_device_capability()[1] >= 9):
                return "cuda_ada"
            return "cuda_ampere"
    except Exception:
        pass
    return "cpu" if system == "Darwin" else DEFAULT_DEVICE


def usable_memory_gb(device: DeviceProfile, stated_memory_gb: float) -> float:
    """Memory a model may actually claim on this device."""
    return round(stated_memory_gb * device.usable_memory_fraction, 2)
