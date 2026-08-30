from __future__ import annotations

import argparse
import sqlite3
import sys

from . import __version__
from .config import Settings, load_settings

_BACK = object()
_FAILURE_REASON_ALIASES = {
    "k": "knowledge_gap",
    "knowledge_gap": "knowledge_gap",
    "r": "retrieval_failure",
    "retrieval_failure": "retrieval_failure",
    "s": "synthesis_needed",
    "synthesis_needed": "synthesis_needed",
    "q": "query_ambiguity",
    "query_ambiguity": "query_ambiguity",
    "?": "unknown",
    "n": "unknown",
    "nevím": "unknown",
    "nevim": "unknown",
    "unknown": "unknown",
}


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
    search_parser.add_argument(
        "--feedback-db",
        default="usage_feedback.db",
        help="SQLite database for real search usage and feedback",
    )
    search_parser.add_argument(
        "--no-feedback",
        action="store_true",
        help="Log the search but skip the interactive rating prompt",
    )
    search_parser.add_argument(
        "--no-log",
        action="store_true",
        help="Do not store this search in the usage database",
    )

    feedback_parser = subparsers.add_parser(
        "feedback",
        help="Add or correct feedback for an already logged search",
    )
    feedback_parser.add_argument(
        "search_id",
        type=int,
        help="Logged search ID",
    )
    feedback_parser.add_argument(
        "--rating",
        type=int,
        choices=(0, 1, 2),
        required=True,
        help="Overall success: 2=found, 1=partly useful, 0=not found",
    )
    feedback_parser.add_argument(
        "--useful",
        default=None,
        help="Comma-separated useful result ranks, for example 1,3,4",
    )
    feedback_parser.add_argument(
        "--reason",
        choices=(
            "knowledge_gap",
            "retrieval_failure",
            "synthesis_needed",
            "query_ambiguity",
            "unknown",
        ),
        default=None,
        help="Primary reason for rating 0/1",
    )
    feedback_parser.add_argument(
        "--note",
        default=None,
        help="Optional free-text note",
    )
    feedback_parser.add_argument(
        "--db",
        default="usage_feedback.db",
        help="SQLite usage database",
    )

    export_parser = subparsers.add_parser(
        "export-feedback",
        help="Export real search usage from SQLite to JSONL",
    )
    export_parser.add_argument(
        "--db",
        default="usage_feedback.db",
        help="SQLite usage database",
    )
    export_parser.add_argument(
        "--output",
        default="evaluation/usage_feedback.jsonl",
        help="UTF-8 JSONL export path",
    )
    export_parser.add_argument(
        "--include-text",
        action="store_true",
        help="Include full retrieved chunk text in the export",
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
        if args.command == "feedback":
            from .usage_feedback import UsageFeedbackStore

            useful_ranks = (
                _parse_useful_ranks(args.useful)
                if args.useful is not None
                else None
            )
            UsageFeedbackStore(args.db).record_feedback(
                args.search_id,
                rating=args.rating,
                useful_ranks=useful_ranks,
                note=args.note,
                failure_reason=args.reason,
            )
            print(f"Feedback for search #{args.search_id} saved.")
            return

        if args.command == "export-feedback":
            from .usage_feedback import UsageFeedbackStore

            count = UsageFeedbackStore(args.db).export_jsonl(
                args.output,
                include_text=args.include_text,
            )
            print(f"Exported {count} searches to: {args.output}")
            print("Review the export before committing it; it contains real user queries.")
            return

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
        else:
            for rank, result in enumerate(results, start=1):
                section = " > ".join(result.section_path) or "(document root)"
                print(f"{rank}. score: {result.score:.3f}")
                print(f"   source: {result.source_path}")
                print(f"   section: {section}")
                print()
                print(_indent(result.text, "   "))
                print()

        _capture_usage(settings, args, results)
    except (FileNotFoundError, ValueError, RuntimeError, sqlite3.Error) as exc:
        parser.error(str(exc))
    except KeyboardInterrupt:
        print("Interrupted.", file=sys.stderr)
        raise SystemExit(130) from None


def _capture_usage(
    settings: Settings,
    args: argparse.Namespace,
    results: list[object],
) -> None:
    if args.no_log:
        return

    from .usage_feedback import UsageFeedbackStore

    top_k = args.top_k if args.top_k is not None else settings.top_k
    try:
        store = UsageFeedbackStore(args.feedback_db)
        search_id = store.record_search(
            query=args.query,
            embedding_model=settings.embedding_model,
            qdrant_collection=settings.qdrant_collection,
            top_k=top_k,
            category=args.category,
            app_version=__version__,
            results=results,
        )
    except (OSError, sqlite3.Error, ValueError) as exc:
        print(f"Warning: could not log search usage: {exc}", file=sys.stderr)
        return

    print(f"Search logged as #{search_id} in {args.feedback_db}.")

    if args.no_feedback or not sys.stdin.isatty():
        return

    while True:
        rating = _prompt_rating()
        if rating is None:
            return

        useful_ranks = None
        if results:
            useful_choice = _prompt_useful_ranks(len(results))
            if useful_choice is _BACK:
                continue
            useful_ranks = useful_choice

        failure_reason = None
        if rating < 2:
            reason_choice = _prompt_failure_reason()
            if reason_choice is _BACK:
                continue
            failure_reason = reason_choice
        break

    try:
        store.record_feedback(
            search_id,
            rating=rating,
            useful_ranks=useful_ranks,
            failure_reason=failure_reason,
        )
    except (OSError, sqlite3.Error, ValueError) as exc:
        print(f"Warning: could not save feedback: {exc}", file=sys.stderr)
        return

    print("Feedback saved.")


def _prompt_rating() -> int | None:
    while True:
        try:
            value = input(
                "Našel jsi, co jsi potřeboval? "
                "[2=ano, 1=částečně, 0=ne, Enter=přeskočit]: "
            ).strip()
        except EOFError:
            return None

        if value == "":
            return None
        if value in {"0", "1", "2"}:
            return int(value)
        print("Zadej 2, 1, 0 nebo Enter.")


def _prompt_useful_ranks(
    result_count: int,
) -> tuple[int, ...] | None | object:
    while True:
        try:
            value = input(
                "Které výsledky byly užitečné? "
                f"[např. 1,3,4; rozsah 1-{result_count}; "
                "b=zpět; Enter=přeskočit]: "
            ).strip()
        except EOFError:
            return None

        if value == "":
            return None
        if value.casefold() in {"b", "z", "zpět", "zpet"}:
            return _BACK

        try:
            return _parse_useful_ranks(value, max_rank=result_count)
        except ValueError:
            print(
                f"Zadej čísla 1-{result_count} oddělená čárkou, "
                "b pro návrat nebo Enter."
            )


def _prompt_failure_reason() -> str | None | object:
    while True:
        try:
            value = input(
                "Pokud odpověď nebyla úplná, proč? "
                "[k=KB chybí/neúplná, r=KB informaci má ale hledání ji nenašlo, "
                "s=informace jsou v několika výsledcích, q=dotaz byl nejasný, "
                "?=nevím, b=zpět, Enter=přeskočit]: "
            ).strip()
        except EOFError:
            return None

        if value == "":
            return None
        if value.casefold() in {"b", "z", "zpět", "zpet"}:
            return _BACK

        reason = _FAILURE_REASON_ALIASES.get(value.casefold())
        if reason is not None:
            return reason

        print("Zadej k, r, s, q, ?, b nebo Enter.")


def _parse_useful_ranks(
    value: str,
    *,
    max_rank: int | None = None,
) -> tuple[int, ...]:
    raw_parts = [part.strip() for part in value.split(",")]
    if not raw_parts or any(part == "" for part in raw_parts):
        raise ValueError("useful ranks must be comma-separated positive integers")

    ranks: set[int] = set()
    for part in raw_parts:
        try:
            rank = int(part)
        except ValueError as exc:
            raise ValueError(
                "useful ranks must be comma-separated positive integers"
            ) from exc

        if rank <= 0 or (max_rank is not None and rank > max_rank):
            raise ValueError("useful rank is outside the available result range")
        ranks.add(rank)

    return tuple(sorted(ranks))


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
