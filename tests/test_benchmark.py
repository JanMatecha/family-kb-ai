from dataclasses import dataclass
from pathlib import Path

import pytest

from family_kb_ai.benchmark import (
    BenchmarkCase,
    BenchmarkCaseResult,
    BenchmarkReport,
    BenchmarkTarget,
    evaluate_results,
    load_benchmark_cases,
)


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
      - source_endswith: b.md
""".strip(),
        encoding="utf-8",
    )

    cases = load_benchmark_cases(cases_path)

    assert len(cases) == 1
    assert cases[0].case_id == "hose"
    assert len(cases[0].targets) == 2
    assert cases[0].targets[1].source_endswith == "b.md"


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
        FakeResult(
            0.8,
            "02_ZAHRADA/SOUHRN.md",
            ("Záhony", "Realizace"),
            "Černá 16mm hadice",
        ),
    ]

    evaluated = evaluate_results(case, results)

    assert evaluated.rank == 2
    assert evaluated.score == pytest.approx(0.8)


def test_source_endswith_matches_without_full_kb_path() -> None:
    case = BenchmarkCase(
        case_id="ladder",
        query="jaký žebřík",
        targets=(
            BenchmarkTarget(
                source_endswith="SOUHRN_ZEBRIKU.md",
                text_contains="3×10",
            ),
        ),
    )
    results = [
        FakeResult(
            0.9,
            "01_DUM/03_VYBAVENI/SOUHRN_ZEBRIKU.md",
            ("Žebřík",),
            "Pro běžné práce 3×10.",
        )
    ]

    evaluated = evaluate_results(case, results)

    assert evaluated.rank == 1


def test_report_metrics_are_case_level_hits() -> None:
    case = BenchmarkCase(
        "a",
        "q",
        (BenchmarkTarget(source_path="a.md"),),
    )
    report = BenchmarkReport(
        cases_path="cases.yaml",
        embedding_model="model",
        collection="kb",
        top_k=100,
        results=(
            BenchmarkCaseResult(case, 1, 0.9, "a.md", ("A",)),
            BenchmarkCaseResult(case, 3, 0.8, "a.md", ("A",)),
            BenchmarkCaseResult(case, 42, 0.7, "a.md", ("A",)),
            BenchmarkCaseResult(case, None, None, None, ()),
        ),
        generated_at="2026-08-28T20:00:00+02:00",
    )

    assert report.hit_rate(1) == pytest.approx(1 / 4)
    assert report.hit_rate(3) == pytest.approx(2 / 4)
    assert report.hit_rate(20) == pytest.approx(2 / 4)
    assert report.hit_rate(100) == pytest.approx(3 / 4)
    assert report.metric_depths() == (1, 3, 5, 10, 20, 100)
    assert report.mrr == pytest.approx((1 + 1 / 3 + 1 / 42) / 4)
