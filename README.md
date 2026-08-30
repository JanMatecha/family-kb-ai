# family-kb-ai

Small local POC for semantic vector search over an external Markdown family knowledge base.

The goal is deliberately narrow: verify that semantic search can find the right knowledge even when the query uses different words than the source Markdown, then improve retrieval based on measured real-world cases.

## Architecture

```text
external RODINNE_KNOWHOW (*.md)
        ↓
Markdown-aware chunking
        ↓
local sentence-transformers embeddings
        ↓
local Qdrant index
        ↓
vector search / retrieval benchmark from CLI
```

**Markdown is the source of truth. Qdrant is only a rebuildable search index.** The knowledge base itself is not stored in this repository. Qdrant can be deleted and rebuilt from the Markdown files at any time.

The default embedding model is `intfloat/multilingual-e5-small`. For E5 models the embedding layer applies the recommended `passage:` and `query:` prefixes. Other sentence-transformers models are embedded without E5 prefixes. Models are downloaded on first use and then run locally.

## Python environment: uv

The project uses **uv** for Python version selection, dependency resolution, virtual-environment management, and command execution.

The repository pins Python 3.10 in `.python-version`. The local `.venv` can still exist, but it is managed by uv; activating it or installing the project with `pip install -e .` is not part of the normal workflow.

Typical update workflow:

```powershell
git pull
uv sync
```

Typical command:

```powershell
uv run family-kb search "kolik máme záhonů?"
```

Tests:

```powershell
uv run pytest
```

`uv.lock` is the reproducible dependency lock file and should be committed to Git. On the first `uv sync`, uv creates it if it is not present.

## Quick start

Requirements: uv, Docker Desktop / Docker Compose, and internet access for the initial dependency and embedding-model downloads.

### 1. Synchronize Python environment

From the repository root:

```powershell
uv sync
```

No PowerShell environment activation is needed.

Check the CLI:

```powershell
uv run family-kb --help
```

### 2. Start Qdrant

```powershell
docker compose up -d
```

Qdrant REST API is exposed only on the local machine at `http://localhost:6333`. The local dashboard is available at `http://localhost:6333/dashboard`.

On the normal Windows notebook you can use the helper:

```powershell
.\start-family-kb.cmd
```

### 3. Configure the external knowledge base

```powershell
Copy-Item config.example.yaml config.yaml
```

Edit `config.yaml` and set `kb_path`, for example:

```yaml
kb_path: "C:/Users/.../RODINNE_KNOWHOW"
```

`config.yaml` is intentionally ignored by Git.

### 4. Full reindex

```powershell
uv run family-kb ingest --recreate
```

The current version intentionally supports an explicit full rebuild. It recursively indexes all `*.md` files under `kb_path`.

### 5. Search

```powershell
uv run family-kb search "jak jsme řešili hadici?"
```

Default output is TOP 5 and includes score, source path, Markdown section hierarchy, and chunk text.

Override result count or add a category filter:

```powershell
uv run family-kb search "jak připojit hadici" --top-k 10
uv run family-kb search "jak připojit hadici" --category 02_ZAHRADA
```

Real searches are logged by the V1.2 pilot feedback layer unless `--no-log` is used.

## Retrieval benchmark (V1.1a)

`benchmarks/retrieval_cases.yaml` contains the original 12-case retrieval baseline. It intentionally includes paraphrases such as `trubka + spojka` versus source text using `hadice + fitinky`.

Run:

```powershell
uv run family-kb benchmark
```

The command searches TOP 20 by default, prints per-case rank/score and aggregate metrics, and writes a UTF-8 report to `benchmark_results.txt`.

Metrics include Hit@K, MRR, and misses at the configured search depth.

## Embedding model comparison (V1.1b)

V1.1b compares embedding models while holding the knowledge base, chunking, benchmark cases, Qdrant search settings, and retrieval logic constant.

Run:

```powershell
uv run family-kb compare-models
```

The default V1.1b models remain:

- `intfloat/multilingual-e5-small`
- `intfloat/multilingual-e5-base`

The command creates separate `*_cmp_*` Qdrant collections and does **not** modify the configured baseline collection.

Reports are written under:

```text
model_comparison_results/
├── benchmark_multilingual_e5_small.txt
├── benchmark_multilingual_e5_base.txt
└── comparison.txt
```

Custom models can be supplied by repeating `--model`.

## Deep retrieval diagnosis (V1.1c)

V1.1c is a diagnostic experiment, not a production search change.

Run:

```powershell
uv run family-kb diagnose-retrieval
```

V1.1c defaults to:

- search depth `TOP 100`,
- `intfloat/multilingual-e5-small`,
- `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`,
- benchmark file `benchmarks/retrieval_cases_v11c.yaml`.

The diagnostic model is intentionally from a different family. The normal E5 query/passage prefixes are not applied to it.

The V1.1c benchmark contains the original 12 garden cases plus six cross-domain cases from:

- `01_DUM`,
- `03_AI_METODIKA`,
- `04_KNIHARSTVI`.

Results are written to:

```text
retrieval_diagnostics/
├── benchmark_multilingual_e5_small.txt
├── benchmark_paraphrase_multilingual_minilm_l12_v2.txt
└── comparison.txt
```

For a baseline collection `family_kb`, V1.1c uses separate experiment collections and does not change the configured baseline collection.

## Pilot feedback (V1.2)

Normal searches can record real usage in local `usage_feedback.db`.

The interactive flow records overall success:

```text
2 = ano
1 = částečně
0 = ne
```

and allows several useful result ranks to be marked, for example:

```text
1,3,4
```

On the useful-results question, `b` returns to the previous rating question.

Correct existing feedback:

```powershell
uv run family-kb feedback 2 --rating 2 --useful 1,3
```

Export real usage for later analysis:

```powershell
uv run family-kb export-feedback
```

The export is written to `evaluation/usage_feedback.jsonl`. Review it before sharing or committing because real family queries can contain private information.

## Benchmark target matching

Benchmark targets can identify a source by exact relative path:

```yaml
source_path: "02_ZAHRADA/02_ZAHONY/SOUHRN_ZAHONU.md"
```

or by path suffix:

```yaml
source_endswith: "SOUHRN_ZEBRIKU.md"
```

Optional `section_contains` and `text_contains` constraints still verify that the returned chunk contains the intended knowledge.

## Configuration

`config.example.yaml` contains:

- `kb_path` – path to the external `RODINNE_KNOWHOW`
- `qdrant_url` – local Qdrant URL
- `qdrant_collection` – collection name, default `family_kb`
- `embedding_model` – local sentence-transformers model used by normal ingest/search/benchmark
- `chunk_size` – maximum approximate chunk length in characters
- `chunk_overlap` – overlap when a long Markdown section must be split
- `top_k` – default number of interactive search results

Chunking first follows Markdown headings (`#`, `##`, `###`, ...). Long sections are then split to the configured size with overlap. Each Qdrant point uses a deterministic UUID derived from source path, section path, and chunk index.

## Tests

Unit tests do not load or download embedding models and do not require a running Qdrant:

```powershell
uv run pytest
```

## Intentionally out of scope

No LLM, chatbot, RAG generation, OpenAI API, web UI, REST API, file watcher, hybrid search, reranker, OCR/PDF ingestion, multimodality, permissions, or cloud deployment.
