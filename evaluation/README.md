# Pilot evaluation data (V1.2a.1)

V1.2a starts collecting **real search usage** instead of optimizing only on hand-written benchmark questions. V1.2a.1 improves the feedback model so one search can mark **multiple returned chunks as useful**.

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
- optional overall user rating,
- zero, one, or several useful result ranks.

After a normal search the CLI asks:

```text
Našel jsi, co jsi potřeboval?
2 = ano
1 = částečně
0 = ne
Enter = přeskočit
```

It then allows several useful results to be marked at once:

```text
Které výsledky byly užitečné?
1,3,4
```

This is intentional: a useful answer can be distributed across several Markdown chunks.

Use `--no-feedback` to keep logging but skip the interactive questions. Use `--no-log` for an intentionally untracked search.

## Correcting feedback later

Feedback for an existing search can be changed without repeating the search. For example:

```powershell
.\.venv\Scripts\family-kb.exe feedback 1 --rating 2 --useful 1,3,4
```

An optional note can be added:

```powershell
.\.venv\Scripts\family-kb.exe feedback 1 --rating 2 --useful 1,3,4 --note "odpověď byla složená z více částí"
```

Existing V1.2a databases are migrated automatically. A previous single `selected_rank` is preserved as one useful rank until that feedback is corrected.

## JSONL export

Export the accumulated usage data with:

```powershell
.\.venv\Scripts\family-kb.exe export-feedback
```

Default output:

```text
evaluation/usage_feedback.jsonl
```

The default export contains real queries, result metadata and feedback, including `useful_ranks`, but **does not include full retrieved chunk text**. Add `--include-text` only when the text is really needed:

```powershell
.\.venv\Scripts\family-kb.exe export-feedback --include-text
```

The JSONL export is intended for later benchmark construction and analysis. It is not automatically committed or uploaded anywhere.

**Privacy:** real queries can reveal family information. Review `evaluation/usage_feedback.jsonl` before committing or sharing it, especially if the GitHub repository is public.
