from family_kb_ai.embeddings import (
    LocalEmbedder,
    chunk_embedding_text,
    resolve_model_revision,
)


PINNED_E5_SMALL_REVISION = "614241f622f53c4eeff9890bdc4f31cfecc418b3"


def test_chunk_embedding_text_includes_section_context() -> None:
    text = chunk_embedding_text(
        ("Zavlažování", "Záhon F", "Montáž hadice"),
        "Pomohlo mírné nahřátí konce hadice.",
    )

    assert text == (
        "Zavlažování > Záhon F > Montáž hadice\n\n"
        "Pomohlo mírné nahřátí konce hadice."
    )


def test_default_e5_small_revision_is_pinned() -> None:
    assert (
        resolve_model_revision("intfloat/multilingual-e5-small")
        == PINNED_E5_SMALL_REVISION
    )


def test_explicit_revision_wins_over_default_pin() -> None:
    assert (
        resolve_model_revision(
            "intfloat/multilingual-e5-small",
            "custom-revision",
        )
        == "custom-revision"
    )


def test_unpinned_model_defaults_to_latest() -> None:
    assert resolve_model_revision("sentence-transformers/example-model") is None


def test_e5_formatting_uses_query_and_passage_prefixes_without_loading_model() -> None:
    embedder = LocalEmbedder.__new__(LocalEmbedder)
    embedder._uses_e5_prefixes = True

    assert embedder._format_query("jak nasadit hadici") == "query: jak nasadit hadici"
    assert embedder._format_passage("text chunku") == "passage: text chunku"


def test_non_e5_formatting_does_not_add_prefixes() -> None:
    embedder = LocalEmbedder.__new__(LocalEmbedder)
    embedder._uses_e5_prefixes = False

    assert embedder._format_query("dotaz") == "dotaz"
    assert embedder._format_passage("pasáž") == "pasáž"
