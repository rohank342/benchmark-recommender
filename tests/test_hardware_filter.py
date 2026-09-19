import pytest

from hardware_filter import (
    WORKSPACE_GB,
    available_precisions,
    best_fit_precision,
    estimate_vram,
    filter_models_by_vram,
    kv_cache_gb,
    max_context_supported,
)

# Qwen2.5-Coder-7B-Instruct's real dimensions: grouped-query attention,
# so only 4 KV heads for 28 attention heads.
QWEN_7B = {
    "model_id": "Qwen/Qwen2.5-Coder-7B-Instruct",
    "params_billion": 7.62,
    "architecture": {
        "num_hidden_layers": 28,
        "num_key_value_heads": 4,
        "head_dim": 128,
        "max_position_embeddings": 32768,
    },
}

AWQ_32B = {
    "model_id": "Qwen/Qwen2.5-Coder-32B-Instruct-AWQ",
    "params_billion": 32.76,
    "architecture": {"native_quant_bits": 4, "native_quant_method": "awq"},
}

GGUF_27B = {
    "model_id": "batiai/Qwen3.6-27B-GGUF",
    "params_billion": 27.0,
    "architecture": {"native_quant_bits": 4, "native_quant_method": "gguf"},
}

UNKNOWN_SIZE = {"model_id": "someone/mystery-gguf", "params_billion": None, "architecture": {}}


class TestKvCache:
    def test_grows_linearly_with_context(self):
        at_4k, _ = kv_cache_gb(QWEN_7B, 4096)
        at_8k, _ = kv_cache_gb(QWEN_7B, 8192)
        assert at_8k == pytest.approx(at_4k * 2, rel=0.02)

    def test_matches_hand_calculation(self):
        # 2 (K+V) x 28 layers x 4 kv heads x 128 dim x 4096 tokens x 2 bytes
        expected = 2 * 28 * 4 * 128 * 4096 * 2 / 1024**3
        cache, estimated = kv_cache_gb(QWEN_7B, 4096)
        assert cache == pytest.approx(expected, abs=0.01)
        assert estimated is False

    def test_falls_back_when_dimensions_are_unknown(self):
        cache, estimated = kv_cache_gb(GGUF_27B, 8192)
        assert cache is not None and estimated is True

    def test_unknown_size_and_dimensions_gives_nothing(self):
        cache, estimated = kv_cache_gb(UNKNOWN_SIZE, 8192)
        assert cache is None and estimated is True


class TestEstimate:
    def test_long_context_dominates_a_small_model(self):
        """The failure the flat 1.5 GB overhead hid."""
        short = estimate_vram(QWEN_7B, "fp16", 4096)
        long = estimate_vram(QWEN_7B, "fp16", 131072)
        assert long.total_gb - short.total_gb > 6  # ~7 GB of extra cache
        assert long.weights_gb == short.weights_gb

    def test_total_is_weights_plus_cache_plus_workspace(self):
        estimate = estimate_vram(QWEN_7B, "fp16", 8192)
        assert estimate.total_gb == pytest.approx(
            estimate.weights_gb + estimate.kv_cache_gb + WORKSPACE_GB, abs=0.01
        )

    def test_lower_precision_shrinks_weights(self):
        fp16 = estimate_vram(QWEN_7B, "fp16", 8192)
        four_bit = estimate_vram(QWEN_7B, "4bit", 8192)
        assert four_bit.weights_gb == pytest.approx(fp16.weights_gb / 4)


class TestNativeQuantization:
    def test_prequantized_repo_offers_only_what_it_ships(self):
        """An AWQ 4-bit repo cannot be run at fp16."""
        assert available_precisions(AWQ_32B) == ("4bit",)
        assert available_precisions(GGUF_27B) == ("4bit",)
        assert estimate_vram(AWQ_32B, "fp16", 8192).available is False

    def test_full_precision_repo_offers_all(self):
        assert available_precisions(QWEN_7B) == ("fp16", "8bit", "4bit")

    def test_gguf_repo_is_not_recommended_at_fp16(self):
        """Regression: a 27B GGUF was being offered at fp16, needing 55 GB."""
        estimate = best_fit_precision(GGUF_27B, available_vram_gb=80, context_tokens=8192)
        assert estimate.precision == "4bit"
        assert estimate.total_gb < 20


class TestFiltering:
    def test_model_that_does_not_fit_is_dropped(self):
        assert filter_models_by_vram([QWEN_7B], available_vram_gb=2) == []

    def test_context_length_costs_precision(self):
        """Same model, same GPU: long context forces a lower precision."""
        short = filter_models_by_vram([QWEN_7B], 18, context_tokens=4096)[0]
        long = filter_models_by_vram([QWEN_7B], 18, context_tokens=131072)[0]
        assert short["best_fit_quant"] == "fp16"
        assert long["best_fit_quant"] == "8bit"

    def test_context_length_can_rule_a_model_out_entirely(self):
        assert filter_models_by_vram([QWEN_7B], 11, context_tokens=4096)
        assert not filter_models_by_vram([QWEN_7B], 11, context_tokens=131072)

    def test_unknown_size_is_surfaced_not_hidden(self):
        """"We don't know" and "it doesn't fit" are different answers."""
        rows = filter_models_by_vram([UNKNOWN_SIZE], available_vram_gb=8)
        assert len(rows) == 1
        assert rows[0]["size_known"] is False
        assert rows[0]["best_fit_quant"] is None

    def test_annotations_explain_the_decision(self):
        row = filter_models_by_vram([QWEN_7B], 24, context_tokens=8192)[0]
        assert row["best_fit_quant"] == "fp16"
        assert row["vram_weights_gb"] and row["vram_kv_cache_gb"]
        assert row["max_context"] == 32768
        assert row["available_precisions"] == "fp16, 8bit, 4bit"


def test_max_context_supported():
    assert max_context_supported(QWEN_7B) == 32768
    assert max_context_supported(UNKNOWN_SIZE) is None
