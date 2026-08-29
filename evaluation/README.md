# Pilot evaluation data (V1.2a)

V1.2a starts collecting **real search usage** instead of optimizing only on hand-written benchmark questions.

## Local SQLite database

Normal interactive searches are stored in:

```text
usage_feedback.db
```

The SQLite file is local-only and is ignored by Git. It contains:

- the exact user query,
- timestamp,
- embedding model and Qdrant collection,
- requested TOP K and optional category,
- returned ranks, chunk IDs, source paths, sections, scores and full chunk text,
- optional user feedback.

After a normal search the CLI asks:

```text
2 = found what I needed
1 = partly useful
0 = did not find it
Enter = skip rating
```

For ratings 1 or 2 it also asks which returned rank was the best result.

Use `--no-feedback` to keep logging but skip the interactive questions. Use `--no-log` for an intentionally untracked search.

## JSONL export

Export the accumulated usage data with:

```powershell
.\.venv\Scripts\family-kb.exe export-feedback
```

Default output:

```text
evaluation/usage_feedback.jsonl
```

The default export contains real queries, result metadata and feedback, but **does not include full retrieved chunk text**. Add `--include-text` only when the text is really needed:

```powershell
.\.venv\Scripts\family-kb.exe export-feedback --include-text
```

The JSONL export is intended for later benchmark construction and analysis. It is not automatically committed or uploaded anywhere.

**Privacy:** real queries can reveal family information. Review `evaluation/usage_feedback.jsonl` before committing or sharing it, especially if the GitHub repository is public.
