from dataclasses import dataclass
from pathlib import Path

import pytest

from family_kb_ai.benchmark import BenchmarkCase, BenchmarkReport, BenchmarkTarget, evaluate_results, load_benchmark_cases


@dataclass(frozen=True)
class FakeResult:
    score: float
    source_path: str
    section_path: tuple[str, ...]
    text: str


def test_load_cases_supports_multiple_targets(tmp_path: Path) -> None:
    cases_path = tmp_path / "cases.yaml"
    cases_path.write_text(
        """
cases:
  - id: hose
    query: jak nasadit trubku
    targets:
      - source_path: 02_ZAHRADA/a.md
        section_contains: Realizace
        text_contains: hadice
      - source_path: 02_ZAHRADA/b.md
""".strip(),
        encoding="utf-8",
    )

    cases = load_benchmark_cases(cases_path)

    assert len(cases) == 1
    assert cases[0].case_id == "hose"
    assert len(cases[0].targets) == 2


def test_evaluate_results_returns_first_acceptable_rank() -> None:
    case = BenchmarkCase(
        case_id="hose",
        query="trubka spojka",
        targets=(
            BenchmarkTarget(
                source_path="02_ZAHRADA/SOUHRN.md",
                section_contains="Realizace",
                text_contains="16mm hadice",
            ),
        ),
    )
    results = [
        FakeResult(0.9, "other.md", ("Other",), "noise"),
        FakeResult(0.8, "02_ZAHRADA/SOUHRN.md", ("Záhony", "Realizace"), "Černá 16mm hadice"),
    ]

    evaluated = evaluate_results(case, results)

    assert evaluated.rank == 2
    assert evaluated.score == pytest.approx(0.8)


def test_report_metrics_are_case_level_hits() -> None:
    case = BenchmarkCase("a", "q", (BenchmarkTarget("a.md"),))
    from family_kb_ai.benchmark import BenchmarkCaseResult

    report = BenchmarkReport(
        cases_path="cases.yaml",
        embedding_model="model",
        collection="kb",
        top_k=20,
        results=(
            BenchmarkCaseResult(case, 1, 0.9, "a.md", ("A",)),
            BenchmarkCaseResult(case, 3, 0.8, "a.md", ("A",)),
            BenchmarkCaseResult(case, None, None, None, ()),
        ),
        generated_at="2026-08-28T20:00:00+02:00",
    )

    assert report.hit_rate(1) == pytest.approx(1 / 3)
    assert report.hit_rate(3) == pytest.approx(2 / 3)
    assert report.mrr == pytest.approx((1 + 1 / 3) / 3)
