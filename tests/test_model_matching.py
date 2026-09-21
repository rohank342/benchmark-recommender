from model_matching import key_from_huggingface_url, match_key, repo_id_from_huggingface_url


def test_hub_repo_and_external_label_agree():
    """The same model named three ways must reduce to one key."""
    key = match_key("Qwen/Qwen2.5-Coder-7B-Instruct")
    assert key == match_key("Qwen2.5 Coder 7B Instruct")
    assert key == match_key("qwen2.5-coder-7b-instruct")


def test_packaging_markers_are_stripped():
    """Reuploads are the same weights, so they match the original model."""
    original = match_key("Qwen/Qwen2.5-Coder-7B-Instruct")
    assert match_key("bartowski/Qwen2.5-Coder-7B-Instruct-GGUF") == original
    assert match_key("Qwen/Qwen2.5-Coder-7B-Instruct-AWQ") == original
    assert match_key("someone/Qwen2.5-Coder-7B-Instruct-Q4_K_M") == original
    assert match_key("codellama/CodeLlama-7b-hf") == match_key("CodeLlama 7b")


def test_different_models_do_not_collide():
    """A false match silently attributes another model's score."""
    assert match_key("Qwen/Qwen2.5-Coder-7B-Instruct") != match_key(
        "Qwen/Qwen2.5-Coder-14B-Instruct"
    )
    # Base and instruct-tuned variants are different models.
    assert match_key("Qwen/Qwen2.5-Coder-7B") != match_key("Qwen/Qwen2.5-Coder-7B-Instruct")
    # Version numbers must survive the "2.5" -> "25" rewrite.
    assert match_key("org/Qwen2.5-Coder-7B") != match_key("org/Qwen2-Coder-7B")
    # A fine-tune of a model is not that model.
    assert match_key("someone/Qwen2.5-Coder-7B-Instruct-abliterated") != match_key(
        "Qwen/Qwen2.5-Coder-7B-Instruct"
    )


def test_empty_and_unidentifying_names():
    assert match_key(None) is None
    assert match_key("") is None
    assert match_key("GGUF") is None  # nothing left after stripping markers


def test_huggingface_url_parsing():
    url = "https://huggingface.co/Qwen/Qwen2.5-Coder-7B-Instruct"
    assert repo_id_from_huggingface_url(url) == "Qwen/Qwen2.5-Coder-7B-Instruct"
    assert key_from_huggingface_url(url) == match_key("Qwen/Qwen2.5-Coder-7B-Instruct")
    assert key_from_huggingface_url(url + "/tree/main") == match_key(
        "Qwen/Qwen2.5-Coder-7B-Instruct"
    )
    assert key_from_huggingface_url(None) is None
    assert key_from_huggingface_url("https://example.com/not-a-model") is None


def test_word_order_does_not_matter():
    """AA labels models "Qwen2.5 Coder Instruct 7B"; the Hub reverses the tail."""
    assert match_key("Qwen/Qwen2.5-Coder-7B-Instruct") == match_key(
        "Qwen2.5 Coder Instruct 7B"
    )
    assert match_key("Qwen/Qwen2.5-Coder-32B-Instruct-AWQ") == match_key(
        "Qwen2.5 Coder Instruct 32B"
    )


def test_reordering_does_not_merge_distinct_models():
    """Order-insensitivity must not erase real differences."""
    assert match_key("Qwen2.5 Coder Instruct 7B") != match_key(
        "Qwen2.5 Coder Instruct 14B"
    )
    assert match_key("Qwen2.5 Coder Instruct 7B") != match_key("Qwen2.5 Coder 7B")
    assert match_key("Qwen3 Coder Next") != match_key("Qwen3 Coder Next GB10")


def test_identity_string_preserves_order_for_org_matching():
    """Org names match by containment, so token order must be kept."""
    from model_matching import identity_string

    assert identity_string("Moonshot AI") == "moonshotai"
    assert identity_string("Z.ai") == "zai"
    # The Hub owner and the benchmark source's creator name should line up.
    assert identity_string("moonshotai") == identity_string("Moonshot AI")
    # match_key sorts tokens, which is exactly why it can't do this job.
    assert match_key("Moonshot AI") != identity_string("Moonshot AI")
