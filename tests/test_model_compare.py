from family_kb_ai.benchmark import (
    BenchmarkCase,
    BenchmarkCaseResult,
    BenchmarkReport,
    BenchmarkTarget,
)
from family_kb_ai.model_compare import (
    DIAGNOSTIC_MODELS,
    ModelComparisonReport,
    ModelRunResult,
    experiment_collection_name,
    model_slug,
)


def _benchmark(
    model: str,
    collection: str,
    ranks: tuple[int | None, ...],
    *,
    top_k: int = 20,
) -> BenchmarkReport:
    results = []
    for index, rank in enumerate(ranks, start=1):
        case = BenchmarkCase(
            f"case_{index}",
            f"query {index}",
            (BenchmarkTarget(source_path="a.md"),),
        )
        results.append(
            BenchmarkCaseResult(
                case=case,
                rank=rank,
                score=None if rank is None else 0.8,
                source_path=None if rank is None else "a.md",
                section_path=(),
            )
        )
    return BenchmarkReport(
        cases_path="cases.yaml",
        embedding_model=model,
        collection=collection,
        top_k=top_k,
        results=tuple(results),
        generated_at="2026-08-28T20:00:00+02:00",
    )


def test_model_slug_is_safe_for_paths_and_collection_names() -> None:
    assert model_slug("intfloat/multilingual-e5-small") == "multilingual_e5_small"
    assert experiment_collection_name(
        "family_kb",
        "intfloat/multilingual-e5-base",
    ) == "family_kb_cmp_multilingual_e5_base"
    assert experiment_collection_name(
        "family_kb",
        "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        tag="diag",
    ) == "family_kb_diag_paraphrase_multilingual_minilm_l12_v2"


def test_diagnostic_models_compare_different_families() -> None:
    assert DIAGNOSTIC_MODELS == (
        "intfloat/multilingual-e5-small",
        "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
    )


def test_comparison_report_renders_deep_metrics_and_case_ranks() -> None:
    small = _benchmark(
        "small",
        "family_kb_diag_small",
        (1, None),
        top_k=100,
    )
    alternate = _benchmark(
        "alternate",
        "family_kb_diag_alt",
        (1, 42),
        top_k=100,
    )
    report = ModelComparisonReport(
        cases_path="cases.yaml",
        top_k=100,
        runs=(
            ModelRunResult(
                "small",
                "small",
                "family_kb_diag_small",
                28,
                333,
                10.0,
                2.0,
                "small.txt",
                small,
            ),
            ModelRunResult(
                "alternate",
                "alternate",
                "family_kb_diag_alt",
                28,
                333,
                20.0,
                3.0,
                "alt.txt",
                alternate,
            ),
        ),
        generated_at="2026-08-28T21:00:00+02:00",
        collection_tag="diag",
    )

    rendered = report.render()

    assert "Family KB embedding model comparison" in rendered
    assert "Experiment tag: diag" in rendered
    assert "Hit@100: 50.0%" in rendered
    assert "case_2 | >100 | 42" in rendered
    assert "family_kb_diag_small" in rendered


def test_benchmark_report_exposes_miss_count() -> None:
    report = _benchmark(
        "small",
        "collection",
        (1, None, 7, None),
    )
    assert report.miss_count == 2
