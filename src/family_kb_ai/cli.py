from __future__ import annotations

import argparse
import sys

from .config import load_settings


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="family-kb")
    parser.add_argument("--config", default="config.yaml", help="Path to YAML config file")
    subparsers = parser.add_subparsers(dest="command", required=True)

    ingest_parser = subparsers.add_parser("ingest", help="Index Markdown knowledge base")
    ingest_parser.add_argument(
        "--recreate",
        action="store_true",
        help="Delete and rebuild the Qdrant collection from Markdown",
    )

    search_parser = subparsers.add_parser("search", help="Semantic vector search")
    search_parser.add_argument("query", help="Natural-language search query")
    search_parser.add_argument("--top-k", type=int, default=None, help="Number of results")
    search_parser.add_argument("--category", default=None, help="Optional category payload filter")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    try:
        settings = load_settings(args.config)
        if args.command == "ingest":
            from .ingest import ingest

            documents, chunks = ingest(settings, recreate=args.recreate)
            print(f"Indexed {documents} Markdown documents into {chunks} chunks.")
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


def _indent(text: str, prefix: str) -> str:
    return "\n".join(f"{prefix}{line}" for line in text.splitlines())
