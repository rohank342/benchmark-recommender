import pytest

from device_profiles import DEVICES, get_device, usable_memory_gb
from hardware_filter import available_precisions, filter_models_by_vram, runnable_on

APPLE = DEVICES["apple_silicon"]
AMPERE = DEVICES["cuda_ampere"]
ADA = DEVICES["cuda_ada"]
BLACKWELL = DEVICES["cuda_blackwell"]
CPU = DEVICES["cpu"]

FULL_7B = {"model_id": "org/model-7b", "params_billion": 7.0, "architecture": {}}
AWQ_7B = {
    "model_id": "org/model-7b-AWQ",
    "params_billion": 7.0,
    "architecture": {"native_quant_method": "awq", "native_quant_bits": 4},
}
GGUF_7B = {
    "model_id": "org/model-7b-GGUF",
    "params_billion": 7.0,
    "architecture": {"native_quant_method": "gguf", "native_quant_bits": 4},
}
MLX_7B = {
    "model_id": "org/model-7b-MLX-4bit",
    "params_billion": 7.0,
    "architecture": {"native_quant_method": "mlx", "native_quant_bits": 4},
}
FP8_7B = {
    "model_id": "org/model-7b-FP8",
    "params_billion": 7.0,
    "architecture": {"native_quant_method": "fp8", "native_quant_bits": 8},
}
NVFP4_7B = {
    "model_id": "org/model-7b-NVFP4",
    "params_billion": 7.0,
    "architecture": {"native_quant_method": "compressed-tensors", "native_quant_bits": 4},
}


class TestRunnability:
    def test_cuda_formats_are_not_offered_to_a_mac(self):
        """The bug that started this: AWQ recommended to a MacBook."""
        assert not runnable_on(AWQ_7B, APPLE)
        assert not runnable_on(FP8_7B, APPLE)
        assert not runnable_on(NVFP4_7B, APPLE)

    def test_mlx_is_not_offered_to_nvidia(self):
        assert not runnable_on(MLX_7B, ADA)
        assert runnable_on(MLX_7B, APPLE)

    def test_gguf_runs_everywhere(self):
        for device in (APPLE, AMPERE, ADA, BLACKWELL, CPU):
            assert runnable_on(GGUF_7B, device)

    def test_full_precision_weights_run_anywhere_with_the_memory(self):
        for device in (APPLE, AMPERE, ADA, BLACKWELL, CPU):
            assert runnable_on(FULL_7B, device)

    def test_fp8_needs_ada_or_newer(self):
        assert not runnable_on(FP8_7B, AMPERE)
        assert runnable_on(FP8_7B, ADA)
        assert runnable_on(FP8_7B, BLACKWELL)

    def test_nvfp4_needs_blackwell(self):
        assert not runnable_on(NVFP4_7B, ADA)
        assert runnable_on(NVFP4_7B, BLACKWELL)


class TestPrecisionAvailability:
    def test_cuda_can_quantize_full_weights_at_load(self):
        assert available_precisions(FULL_7B, ADA) == ("fp16", "8bit", "4bit")

    def test_apple_silicon_cannot(self):
        """bitsandbytes has no working MPS path — fp16 or a GGUF/MLX build."""
        assert available_precisions(FULL_7B, APPLE) == ("fp16",)

    def test_prequantized_artifacts_offer_only_what_they_are(self):
        assert available_precisions(GGUF_7B, APPLE) == ("4bit",)
        assert available_precisions(MLX_7B, APPLE) == ("4bit",)

    def test_unrunnable_artifact_offers_nothing(self):
        assert available_precisions(AWQ_7B, APPLE) == ()


class TestFiltering:
    def test_mac_user_is_not_shown_cuda_artifacts(self):
        rows = filter_models_by_vram([AWQ_7B, GGUF_7B], 24, 8192, APPLE)
        assert [r["model_id"] for r in rows] == ["org/model-7b-GGUF"]

    def test_same_budget_differs_by_device(self):
        """7B at fp16 needs ~16 GB; CUDA can drop to 4-bit, Apple can't."""
        on_cuda = filter_models_by_vram([FULL_7B], 12, 8192, ADA)
        on_apple = filter_models_by_vram([FULL_7B], 12, 8192, APPLE)
        assert on_cuda and on_cuda[0]["best_fit_quant"] == "8bit"
        assert not on_apple  # fp16 only, and fp16 doesn't fit in 12 GB

    def test_runtime_format_is_reported(self):
        row = filter_models_by_vram([GGUF_7B], 24, 8192, APPLE)[0]
        assert row["runtime_format"] == "gguf"


class TestMemoryBudget:
    def test_unified_memory_reserves_a_share_for_the_os(self):
        assert usable_memory_gb(APPLE, 24) == pytest.approx(16.8)

    def test_discrete_vram_gives_up_only_a_sliver(self):
        assert usable_memory_gb(ADA, 24) == pytest.approx(22.8)

    def test_unknown_device_key_falls_back_to_a_default(self):
        assert get_device(None).key in DEVICES
        assert get_device("not-a-device").key in DEVICES
