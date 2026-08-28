from __future__ import annotations

import argparse
import sys

from .config import load_settings


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="family-kb")
    parser.add_argument(
        "--config",
        default="config.yaml",
        help="Path to YAML config file",
    )
    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
    )

    ingest_parser = subparsers.add_parser(
        "ingest",
        help="Index Markdown knowledge base",
    )
    ingest_parser.add_argument(
        "--recreate",
        action="store_true",
        help="Delete and rebuild the Qdrant collection from Markdown",
    )

    search_parser = subparsers.add_parser(
        "search",
        help="Semantic vector search",
    )
    search_parser.add_argument(
        "query",
        help="Natural-language search query",
    )
    search_parser.add_argument(
        "--top-k",
        type=int,
        default=None,
        help="Number of results",
    )
    search_parser.add_argument(
        "--category",
        default=None,
        help="Optional category payload filter",
    )

    benchmark_parser = subparsers.add_parser(
        "benchmark",
        help="Run reproducible retrieval quality cases",
    )
    benchmark_parser.add_argument(
        "--cases",
        default="benchmarks/retrieval_cases.yaml",
        help="YAML file with retrieval benchmark cases",
    )
    benchmark_parser.add_argument(
        "--top-k",
        type=int,
        default=20,
        help="Search depth used to find an acceptable result",
    )
    benchmark_parser.add_argument(
        "--output",
        default="benchmark_results.txt",
        help="UTF-8 text report path",
    )

    compare_parser = subparsers.add_parser(
        "compare-models",
        help="Reindex and compare embedding models on the same benchmark",
    )
    _add_model_comparison_arguments(
        compare_parser,
        default_cases="benchmarks/retrieval_cases.yaml",
        default_top_k=20,
        default_output_dir="model_comparison_results",
    )

    diagnose_parser = subparsers.add_parser(
        "diagnose-retrieval",
        help="Deep TOP-100 retrieval diagnosis across different multilingual model families",
    )
    _add_model_comparison_arguments(
        diagnose_parser,
        default_cases="benchmarks/retrieval_cases_v11c.yaml",
        default_top_k=100,
        default_output_dir="retrieval_diagnostics",
    )

    return parser


def _add_model_comparison_arguments(
    parser: argparse.ArgumentParser,
    *,
    default_cases: str,
    default_top_k: int,
    default_output_dir: str,
) -> None:
    parser.add_argument(
        "--model",
        dest="models",
        action="append",
        default=None,
        help=(
            "Embedding model to compare; repeat for multiple models. "
            "Command-specific defaults are used when omitted."
        ),
    )
    parser.add_argument(
        "--cases",
        default=default_cases,
        help="YAML file with retrieval benchmark cases",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=default_top_k,
        help="Search depth used for every model",
    )
    parser.add_argument(
        "--output-dir",
        default=default_output_dir,
        help="Directory for UTF-8 per-model and comparison reports",
    )


def main() -> None:
    _configure_utf8_streams()
    parser = build_parser()
    args = parser.parse_args()

    try:
        settings = load_settings(args.config)
        if args.command == "ingest":
            from .ingest import ingest

            documents, chunks = ingest(
                settings,
                recreate=args.recreate,
            )
            print(f"Indexed {documents} Markdown documents into {chunks} chunks.")
            return

        if args.command == "benchmark":
            from .benchmark import run_benchmark

            report = run_benchmark(
                settings,
                cases_path=args.cases,
                top_k=args.top_k,
                output_path=args.output,
            )
            print(report.render(), end="")
            print(f"UTF-8 report saved to: {args.output}")
            return

        if args.command in {"compare-models", "diagnose-retrieval"}:
            from .model_compare import (
                DEFAULT_MODELS,
                DIAGNOSTIC_MODELS,
                run_model_comparison,
            )

            if args.models:
                models = tuple(args.models)
            elif args.command == "diagnose-retrieval":
                models = DIAGNOSTIC_MODELS
            else:
                models = DEFAULT_MODELS

            collection_tag = "diag" if args.command == "diagnose-retrieval" else "cmp"
            report = run_model_comparison(
                settings,
                models=models,
                cases_path=args.cases,
                top_k=args.top_k,
                output_dir=args.output_dir,
                collection_tag=collection_tag,
            )
            print(report.render(), end="")
            print(f"UTF-8 comparison saved to: {args.output_dir}/comparison.txt")
            return

        from .search import search

        results = search(
            settings,
            args.query,
            top_k=args.top_k,
            category=args.category,
        )
        if not results:
            print("No results.")
            return

        for rank, result in enumerate(results, start=1):
            section = " > ".join(result.section_path) or "(document root)"
            print(f"{rank}. score: {result.score:.3f}")
            print(f"   source: {result.source_path}")
            print(f"   section: {section}")
            print()
            print(_indent(result.text, "   "))
            print()
    except (FileNotFoundError, ValueError, RuntimeError) as exc:
        parser.error(str(exc))
    except KeyboardInterrupt:
        print("Interrupted.", file=sys.stderr)
        raise SystemExit(130) from None


def _configure_utf8_streams() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except (AttributeError, OSError):
                pass


def _indent(text: str, prefix: str) -> str:
    return "\n".join(f"{prefix}{line}" for line in text.splitlines())
