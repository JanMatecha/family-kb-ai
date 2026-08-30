# Pilot evaluation data (V1.2b)

V1.2 starts collecting **real search usage** instead of optimizing only on hand-written benchmark questions. V1.2a.1 allows one search to mark **multiple returned chunks as useful**. V1.2a.2 adds a **back** action. V1.2b adds a **primary failure reason** for unsuccessful or only partly successful searches so later analysis can distinguish missing knowledge from retrieval problems.

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
- zero, one, or several useful result ranks,
- optional primary failure reason for rating `0` or `1`.

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

At this second prompt, `b` (also `z`, `zpet`, or `zpět`) returns to the overall `2/1/0` rating question without saving the feedback yet.

For rating `0` or `1`, the CLI additionally asks for the primary reason:

```text
k = knowledge_gap
    KB informaci nemá, má ji neúplnou nebo neověřenou

r = retrieval_failure
    informace v KB pravděpodobně je, ale vyhledávání ji nenašlo

s = synthesis_needed
    potřebné informace jsou rozdělené mezi více výsledků

q = query_ambiguity
    dotaz byl nejasný nebo měl více možných významů

? = unknown
    uživatel nedokáže příčinu spolehlivě určit
```

`b` se z této otázky vrátí na začátek feedbacku a `Enter` příčinu přeskočí. `unknown` je záměrná hodnota: uživatel nemá být nucen hádat, zda je problém v KB nebo ve vyhledávání.

Use `--no-feedback` to keep logging but skip the interactive questions. Use `--no-log` for an intentionally untracked search.

## Correcting feedback later

Feedback for an existing search can be changed without repeating the search. For example:

```powershell
uv run family-kb feedback 1 --rating 2 --useful 1,3,4
```

For an unsuccessful or partial result, add a primary reason:

```powershell
uv run family-kb feedback 2 --rating 1 --useful 3 --reason knowledge_gap
```

Supported `--reason` values are:

```text
knowledge_gap
retrieval_failure
synthesis_needed
query_ambiguity
unknown
```

An optional note can be added:

```powershell
uv run family-kb feedback 2 --rating 1 --useful 3 --reason knowledge_gap --note "chybí přesná nadmořská výška záhonů"
```

A `rating=2` cannot have a failure reason. Correcting an older `0/1` feedback to `2` clears the previous failure reason automatically.

Existing V1.2a databases are migrated automatically. A new nullable `failure_reason` column is added to `feedback`; existing ratings and useful ranks are preserved. A previous single `selected_rank` is still migrated to one useful rank.

## JSONL export

Export the accumulated usage data with:

```powershell
uv run family-kb export-feedback
```

Default output:

```text
evaluation/usage_feedback.jsonl
```

The default export contains real queries, result metadata and feedback, including `useful_ranks` and `failure_reason`, but **does not include full retrieved chunk text**. Add `--include-text` only when the text is really needed:

```powershell
uv run family-kb export-feedback --include-text
```

The classification is **user feedback, not ground truth**. Later evaluation can independently inspect the full original KB and verify whether a reported `knowledge_gap` or `retrieval_failure` was classified correctly.

The JSONL export is intended for later benchmark construction and analysis. It is not automatically committed or uploaded anywhere.

**Privacy:** real queries can reveal family information. Review `evaluation/usage_feedback.jsonl` before committing or sharing it, especially if the GitHub repository is public.
