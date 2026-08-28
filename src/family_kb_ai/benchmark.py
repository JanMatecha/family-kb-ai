from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Sequence

import yaml

if TYPE_CHECKING:
    from .config import Settings


@dataclass(frozen=True)
class BenchmarkTarget:
    source_path: str
    section_contains: str | None = None
    text_contains: str | None = None


@dataclass(frozen=True)
class BenchmarkCase:
    case_id: str
    query: str
    targets: tuple[BenchmarkTarget, ...]
    category: str | None = None


@dataclass(frozen=True)
class BenchmarkCaseResult:
    case: BenchmarkCase
    rank: int | None
    score: float | None
    source_path: str | None
    section_path: tuple[str, ...]


@dataclass(frozen=True)
class BenchmarkReport:
    cases_path: str
    embedding_model: str
    collection: str
    top_k: int
    results: tuple[BenchmarkCaseResult, ...]
    generated_at: str

    @property
    def mrr(self) -> float:
        if not self.results:
            return 0.0
        return sum(0.0 if item.rank is None else 1.0 / item.rank for item in self.results) / len(self.results)

    def hit_rate(self, k: int) -> float:
        if not self.results:
            return 0.0
        return sum(1 for item in self.results if item.rank is not None and item.rank <= k) / len(self.results)

    @property
    def miss_count(self) -> int:
        return sum(1 for item in self.results if item.rank is None)

    def render(self) -> str:
        lines = [
            "Family KB retrieval benchmark",
            f"Generated: {self.generated_at}",
            f"Cases: {self.cases_path}",
            f"Embedding model: {self.embedding_model}",
            f"Qdrant collection: {self.collection}",
            f"Search depth: TOP {self.top_k}",
            "",
            "RESULTS",
            "=======",
        ]

        for index, item in enumerate(self.results, start=1):
            status = "PASS" if item.rank is not None else "MISS"
            rank = str(item.rank) if item.rank is not None else f">{self.top_k}"
            score = f"{item.score:.3f}" if item.score is not None else "-"
            lines.extend(
                [
                    f"{index:02d}. {status}  rank={rank}  score={score}  id={item.case.case_id}",
                    f"    query: {item.case.query}",
                ]
            )
            if item.source_path:
                section = " > ".join(item.section_path) or "(document root)"
                lines.extend(
                    [
                        f"    source: {item.source_path}",
                        f"    section: {section}",
                    ]
                )
            lines.append("")

        total = len(self.results)
        lines.extend(
            [
                "METRICS",
                "=======",
                _format_hit_metric("Hit@1", self.hit_rate(1), total),
                _format_hit_metric("Hit@3", self.hit_rate(3), total),
                _format_hit_metric("Hit@5", self.hit_rate(5), total),
                f"MRR: {self.mrr:.3f}",
                f"Misses@{self.top_k}: {self.miss_count}",
                "",
                "Hit@K means that at least one acceptable target for the case appeared in TOP K.",
            ]
        )
        return "\n".join(lines) + "\n"


def load_benchmark_cases(path: str | Path) -> list[BenchmarkCase]:
    benchmark_path = Path(path)
    if not benchmark_path.exists():
        raise FileNotFoundError(f"Benchmark cases file not found: {benchmark_path}")

    data = yaml.safe_load(benchmark_path.read_text(encoding="utf-8"))
    raw_cases = data.get("cases") if isinstance(data, dict) else data
    if not isinstance(raw_cases, list) or not raw_cases:
        raise ValueError("Benchmark file must contain a non-empty 'cases' list")

    cases: list[BenchmarkCase] = []
    seen_ids: set[str] = set()
    for index, raw_case in enumerate(raw_cases, start=1):
        if not isinstance(raw_case, dict):
            raise ValueError(f"Benchmark case {index} must be a mapping")

        case_id = str(raw_case.get("id", "")).strip()
        query = str(raw_case.get("query", "")).strip()
        raw_targets = raw_case.get("targets")
        if not case_id:
            raise ValueError(f"Benchmark case {index} is missing id")
        if case_id in seen_ids:
            raise ValueError(f"Duplicate benchmark case id: {case_id}")
        if not query:
            raise ValueError(f"Benchmark case '{case_id}' is missing query")
        if not isinstance(raw_targets, list) or not raw_targets:
            raise ValueError(f"Benchmark case '{case_id}' must define at least one target")

        targets: list[BenchmarkTarget] = []
        for raw_target in raw_targets:
            if not isinstance(raw_target, dict):
                raise ValueError(f"Targets for '{case_id}' must be mappings")
            source_path = str(raw_target.get("source_path", "")).strip()
            if not source_path:
                raise ValueError(f"Target for '{case_id}' is missing source_path")
            targets.append(
                BenchmarkTarget(
                    source_path=source_path.replace("\\", "/"),
                    section_contains=_optional_text(raw_target.get("section_contains")),
                    text_contains=_optional_text(raw_target.get("text_contains")),
                )
            )

        category = _optional_text(raw_case.get("category"))
        cases.append(BenchmarkCase(case_id, query, tuple(targets), category))
        seen_ids.add(case_id)

    return cases


def evaluate_results(case: BenchmarkCase, results: Sequence[Any]) -> BenchmarkCaseResult:
    for rank, result in enumerate(results, start=1):
        if any(_matches(result, target) for target in case.targets):
            return BenchmarkCaseResult(
                case=case,
                rank=rank,
                score=float(result.score),
                source_path=str(result.source_path),
                section_path=tuple(result.section_path),
            )
    return BenchmarkCaseResult(case, None, None, None, ())


def run_benchmark(
    settings: "Settings",
    *,
    cases_path: str | Path,
    top_k: int,
    output_path: str | Path,
    embedder: Any | None = None,
    store: Any | None = None,
) -> BenchmarkReport:
    if top_k <= 0:
        raise ValueError("benchmark top_k must be greater than 0")

    if embedder is None:
        from .embeddings import LocalEmbedder

        embedder = LocalEmbedder(settings.embedding_model)
    if store is None:
        from .qdrant_store import QdrantStore

        store = QdrantStore(settings.qdrant_url, settings.qdrant_collection)

    from .search import search_with_components

    cases = load_benchmark_cases(cases_path)
    evaluated: list[BenchmarkCaseResult] = []
    for case in cases:
        results = search_with_components(
            case.query,
            embedder=embedder,
            store=store,
            top_k=top_k,
            category=case.category,
        )
        evaluated.append(evaluate_results(case, results))

    report = BenchmarkReport(
        cases_path=str(cases_path),
        embedding_model=settings.embedding_model,
        collection=settings.qdrant_collection,
        top_k=top_k,
        results=tuple(evaluated),
        generated_at=datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
    )
    Path(output_path).write_text(report.render(), encoding="utf-8")
    return report


def _matches(result: Any, target: BenchmarkTarget) -> bool:
    if _normalize_path(str(result.source_path)) != _normalize_path(target.source_path):
        return False

    if target.section_contains:
        section = " > ".join(result.section_path)
        if _normalize_text(target.section_contains) not in _normalize_text(section):
            return False

    if target.text_contains:
        if _normalize_text(target.text_contains) not in _normalize_text(str(result.text)):
            return False

    return True


def _normalize_path(value: str) -> str:
    return value.replace("\\", "/").casefold().strip()


def _normalize_text(value: str) -> str:
    return " ".join(value.casefold().split())


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _format_hit_metric(name: str, rate: float, total: int) -> str:
    hits = round(rate * total)
    return f"{name}: {rate * 100:.1f}% ({hits}/{total})"
