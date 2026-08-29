from family_kb_ai.embeddings import LocalEmbedder, chunk_embedding_text


def test_chunk_embedding_text_includes_section_context() -> None:
    text = chunk_embedding_text(
        ("Zavlažování", "Záhon F", "Montáž hadice"),
        "Pomohlo mírné nahřátí konce hadice.",
    )

    assert text == (
        "Zavlažování > Záhon F > Montáž hadice\n\n"
        "Pomohlo mírné nahřátí konce hadice."
    )


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
