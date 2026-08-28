from family_kb_ai.benchmark import (
    BenchmarkCase,
    BenchmarkCaseResult,
    BenchmarkReport,
    BenchmarkTarget,
)
from family_kb_ai.model_compare import (
    ModelComparisonReport,
    ModelRunResult,
    experiment_collection_name,
    model_slug,
)


def _benchmark(model: str, collection: str, ranks: tuple[int | None, ...]) -> BenchmarkReport:
    results = []
    for index, rank in enumerate(ranks, start=1):
        case = BenchmarkCase(
            f"case_{index}",
            f"query {index}",
            (BenchmarkTarget("a.md"),),
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
        top_k=20,
        results=tuple(results),
        generated_at="2026-08-28T20:00:00+02:00",
    )


def test_model_slug_is_safe_for_paths_and_collection_names() -> None:
    assert model_slug("intfloat/multilingual-e5-small") == "multilingual_e5_small"
    assert experiment_collection_name("family_kb", "intfloat/multilingual-e5-base") == (
        "family_kb_cmp_multilingual_e5_base"
    )


def test_comparison_report_renders_metrics_and_case_ranks() -> None:
    small = _benchmark("small", "family_kb_cmp_small", (1, None))
    base = _benchmark("base", "family_kb_cmp_base", (1, 4))
    report = ModelComparisonReport(
        cases_path="cases.yaml",
        top_k=20,
        runs=(
            ModelRunResult("small", "small", "family_kb_cmp_small", 28, 333, 10.0, 2.0, "small.txt", small),
            ModelRunResult("base", "base", "family_kb_cmp_base", 28, 333, 20.0, 3.0, "base.txt", base),
        ),
        generated_at="2026-08-28T21:00:00+02:00",
    )

    rendered = report.render()

    assert "Family KB embedding model comparison" in rendered
    assert "Hit@1: 50.0%" in rendered
    assert "case_2 | >20 | 4" in rendered
    assert "family_kb_cmp_small" in rendered


def test_benchmark_report_exposes_miss_count() -> None:
    report = _benchmark("small", "collection", (1, None, 7, None))
    assert report.miss_count == 2
