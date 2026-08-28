from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
import gc
import re
from typing import TYPE_CHECKING, Sequence

from .benchmark import BenchmarkReport

if TYPE_CHECKING:
    from .config import Settings


DEFAULT_MODELS = (
    "intfloat/multilingual-e5-small",
    "intfloat/multilingual-e5-base",
)


@dataclass(frozen=True)
class ModelRunResult:
    model: str
    slug: str
    collection: str
    document_count: int
    chunk_count: int
    index_seconds: float
    benchmark_seconds: float
    benchmark_output: str
    benchmark: BenchmarkReport


@dataclass(frozen=True)
class ModelComparisonReport:
    cases_path: str
    top_k: int
    runs: tuple[ModelRunResult, ...]
    generated_at: str

    def render(self) -> str:
        lines = [
            "Family KB embedding model comparison",
            f"Generated: {self.generated_at}",
            f"Cases: {self.cases_path}",
            f"Search depth: TOP {self.top_k}",
            "",
            "MODEL SUMMARY",
            "=============",
        ]

        for index, run in enumerate(self.runs, start=1):
            report = run.benchmark
            lines.extend(
                [
                    f"{index}. {run.model}",
                    f"   collection: {run.collection}",
                    f"   indexed: {run.document_count} documents / {run.chunk_count} chunks",
                    f"   Hit@1: {report.hit_rate(1) * 100:.1f}%",
                    f"   Hit@3: {report.hit_rate(3) * 100:.1f}%",
                    f"   Hit@5: {report.hit_rate(5) * 100:.1f}%",
                    f"   MRR: {report.mrr:.3f}",
                    f"   Misses@{self.top_k}: {report.miss_count}",
                    f"   index time: {run.index_seconds:.1f} s",
                    f"   benchmark time: {run.benchmark_seconds:.1f} s",
                    f"   detailed report: {run.benchmark_output}",
                    "",
                ]
            )

        lines.extend(["CASE RANKS", "=========="])
        if self.runs:
            header = "case id" + "".join(f" | {run.slug}" for run in self.runs)
            lines.append(header)
            lines.append("-" * len(header))
            case_ids = [item.case.case_id for item in self.runs[0].benchmark.results]
            result_maps = [
                {item.case.case_id: item for item in run.benchmark.results}
                for run in self.runs
            ]
            for case_id in case_ids:
                ranks = []
                for result_map in result_maps:
                    item = result_map.get(case_id)
                    if item is None or item.rank is None:
                        ranks.append(f">{self.top_k}")
                    else:
                        ranks.append(str(item.rank))
                lines.append(case_id + "".join(f" | {rank}" for rank in ranks))

        lines.extend(
            [
                "",
                "Lower rank and higher Hit@K/MRR are better. Runtime is informational only.",
                "Experiment collections are separate from the configured baseline collection.",
            ]
        )
        return "\n".join(lines) + "\n"


def model_slug(model_name: str) -> str:
    tail = model_name.rsplit("/", 1)[-1].casefold()
    slug = re.sub(r"[^a-z0-9]+", "_", tail).strip("_")
    if not slug:
        raise ValueError(f"Cannot derive model slug from: {model_name}")
    return slug


def experiment_collection_name(base_collection: str, model_name: str) -> str:
    return f"{base_collection}_cmp_{model_slug(model_name)}"


def run_model_comparison(
    settings: "Settings",
    *,
    models: Sequence[str] = DEFAULT_MODELS,
    cases_path: str | Path,
    top_k: int,
    output_dir: str | Path,
) -> ModelComparisonReport:
    normalized_models = tuple(dict.fromkeys(model.strip() for model in models if model.strip()))
    if len(normalized_models) < 2:
        raise ValueError("compare-models requires at least two distinct models")
    if top_k <= 0:
        raise ValueError("compare-models top_k must be greater than 0")

    from .benchmark import run_benchmark
    from .embeddings import LocalEmbedder
    from .ingest import collect_chunks, index_chunks
    from .qdrant_store import QdrantStore

    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    indexed_at = datetime.now(timezone.utc).isoformat()
    chunks = collect_chunks(settings, indexed_at)
    document_count = len({chunk.source_path for chunk in chunks})

    runs: list[ModelRunResult] = []
    for model in normalized_models:
        slug = model_slug(model)
        collection = experiment_collection_name(settings.qdrant_collection, model)
        experiment_settings = replace(
            settings,
            embedding_model=model,
            qdrant_collection=collection,
        )

        embedder = LocalEmbedder(model)
        store = QdrantStore(settings.qdrant_url, collection)

        index_start = perf_counter()
        index_chunks(chunks, embedder=embedder, store=store)
        index_seconds = perf_counter() - index_start

        benchmark_output = output_root / f"benchmark_{slug}.txt"
        benchmark_start = perf_counter()
        benchmark = run_benchmark(
            experiment_settings,
            cases_path=cases_path,
            top_k=top_k,
            output_path=benchmark_output,
            embedder=embedder,
            store=store,
        )
        benchmark_seconds = perf_counter() - benchmark_start

        runs.append(
            ModelRunResult(
                model=model,
                slug=slug,
                collection=collection,
                document_count=document_count,
                chunk_count=len(chunks),
                index_seconds=index_seconds,
                benchmark_seconds=benchmark_seconds,
                benchmark_output=str(benchmark_output),
                benchmark=benchmark,
            )
        )
        del embedder, store
        gc.collect()

    report = ModelComparisonReport(
        cases_path=str(cases_path),
        top_k=top_k,
        runs=tuple(runs),
        generated_at=datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
    )
    (output_root / "comparison.txt").write_text(report.render(), encoding="utf-8")
    return report
