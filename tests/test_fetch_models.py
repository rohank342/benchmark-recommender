from types import SimpleNamespace

from fetch_models import (
    MIN_DOWNLOADS_FOR_PROVENANCE,
    MIN_LIKES_FOR_PROVENANCE,
    _has_real_weights,
    _owner_matches_creator,
    _provenance_verified,
)


def _info(repo_id, downloads=0, likes=0, params=7_000_000_000, pipeline="text-generation"):
    return SimpleNamespace(
        id=repo_id,
        downloads=downloads,
        likes=likes,
        pipeline_tag=pipeline,
        safetensors=SimpleNamespace(total=params) if params else None,
    )


class TestOwnerMatchesCreator:
    def test_direct_name_match(self):
        assert _owner_matches_creator("Qwen/Qwen3-Coder", "Qwen")
        assert _owner_matches_creator("ibm-granite/granite-4.2-8b", "IBM")
        assert _owner_matches_creator("moonshotai/Kimi-K2.6", "Moonshot AI")

    def test_initials_match(self):
        """Publishers abbreviate: "Institute of Foundation Models" -> IFM."""
        assert _owner_matches_creator("IFM/K2-Horizon-7B", "Institute of Foundation Models")

    def test_unrelated_owner_does_not_match(self):
        assert not _owner_matches_creator("testaccount-ai/Qwen3.8-Max", "Alibaba")
        assert not _owner_matches_creator("Qwen/Qwen3-Coder", None)


class TestProvenance:
    def test_publisher_org_is_enough_on_its_own(self):
        assert _provenance_verified(_info("Qwen/Qwen3-Coder"), "Qwen")

    def test_adoption_vouches_for_a_brand_mismatch(self):
        """"Kimi" isn't `moonshotai`, but half a million pulls are evidence."""
        info = _info("moonshotai/Kimi-K2.6", downloads=521_957, likes=1_608)
        assert _provenance_verified(info, "Kimi")

    def test_likes_alone_can_vouch(self):
        info = _info("OpenHands/openhands-lm-32b-v0.1", downloads=88, likes=392)
        assert _provenance_verified(info, "Some Other Org")

    def test_impersonation_is_not_verified(self):
        """The testaccount-ai/Qwen3.8-Max case: no org match, no adoption."""
        info = _info("testaccount-ai/Qwen3.8-Max", downloads=339, likes=2)
        assert not _provenance_verified(info, "Alibaba")

    def test_thresholds_are_boundaries_not_gaps(self):
        assert _provenance_verified(_info("x/y", downloads=MIN_DOWNLOADS_FOR_PROVENANCE), "z")
        assert _provenance_verified(_info("x/y", likes=MIN_LIKES_FOR_PROVENANCE), "z")
        assert not _provenance_verified(
            _info("x/y", downloads=MIN_DOWNLOADS_FOR_PROVENANCE - 1, likes=MIN_LIKES_FOR_PROVENANCE - 1),
            "z",
        )


class TestHasRealWeights:
    def test_weights_required(self):
        """`Xenova/gpt-3.5-turbo` is a tokenizer repo, not the model."""
        assert not _has_real_weights(_info("Xenova/gpt-3.5-turbo", params=None))

    def test_multimodal_chat_models_count(self):
        """Kimi is tagged image-text-to-text but still writes code."""
        assert _has_real_weights(_info("moonshotai/Kimi-K2.6", pipeline="image-text-to-text"))

    def test_other_pipelines_are_rejected(self):
        assert not _has_real_weights(_info("org/an-embedder", pipeline="sentence-similarity"))
