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

The default embedding model is `intfloat/multilingual-e5-small`. For E5 models the embedding layer applies the recommended `passage:` and `query:` prefixes. The model is downloaded on first use and then runs locally.

## Quick start

Requirements: Python 3.10+, Docker Desktop / Docker Compose, and internet access for the first embedding-model download.

### 1. Create a Python environment and install

PowerShell:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e .
```

If PowerShell activation is blocked by execution policy, the virtual environment can be used explicitly without activation:

```powershell
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\family-kb.exe --help
```

For development/tests:

```powershell
pip install -e ".[dev]"
```

### 2. Start Qdrant

```powershell
docker compose up -d
```

Qdrant REST API is exposed only on the local machine at `http://localhost:6333`. The local dashboard is available at `http://localhost:6333/dashboard`.

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
family-kb ingest --recreate
```

The current version intentionally supports an explicit full rebuild. It recursively indexes all `*.md` files under `kb_path`.

### 5. Search

```powershell
family-kb search "jak jsme řešili hadici?"
```

Default output is TOP 5 and includes score, source path, Markdown section hierarchy, and chunk text.

Override result count or add a category filter:

```powershell
family-kb search "jak připojit hadici" --top-k 10
family-kb search "jak připojit hadici" --category 02_ZAHRADA
```

## Retrieval benchmark (V1.1a)

`benchmarks/retrieval_cases.yaml` contains a small set of real retrieval cases with one or more acceptable target chunks. The starter set intentionally includes paraphrases such as `trubka + spojka` versus source text using `hadice + fitinky`.

Run the benchmark against the currently indexed Qdrant collection:

```powershell
family-kb benchmark
```

On Windows without virtual-environment activation:

```powershell
.\.venv\Scripts\family-kb.exe benchmark
```

The command searches TOP 20 by default, prints per-case rank/score and aggregate metrics, and writes a UTF-8 report to:

```text
benchmark_results.txt
```

Useful options:

```powershell
family-kb benchmark --top-k 30
family-kb benchmark --cases benchmarks/retrieval_cases.yaml --output benchmark_e5_small.txt
```

Metrics are deliberately simple:

- `Hit@1`, `Hit@3`, `Hit@5` – fraction of cases where at least one acceptable target appears in TOP K,
- `MRR` – mean reciprocal rank of the first acceptable target,
- `Misses@N` – cases with no acceptable target within the configured search depth.

The benchmark loads the embedding model once for the whole run. This makes repeated retrieval tests faster and gives a reproducible baseline for later model/chunking comparisons.

## Embedding model comparison (V1.1b)

V1.1b compares embedding models while holding the knowledge base, chunking, benchmark cases, Qdrant search settings, and retrieval logic constant.

Run the default comparison:

```powershell
family-kb compare-models
```

On Windows without virtual-environment activation:

```powershell
.\.venv\Scripts\family-kb.exe compare-models
```

The default models are:

- `intfloat/multilingual-e5-small`
- `intfloat/multilingual-e5-base`

The command collects the Markdown chunks once, then creates a separate Qdrant collection for each model, re-embeds the same chunks, runs the same retrieval benchmark, and writes UTF-8 reports under:

```text
model_comparison_results/
├── benchmark_multilingual_e5_small.txt
├── benchmark_multilingual_e5_base.txt
└── comparison.txt
```

For a configured baseline collection named `family_kb`, the experiment collections are:

```text
family_kb_cmp_multilingual_e5_small
family_kb_cmp_multilingual_e5_base
```

The configured baseline collection itself is **not modified or deleted** by `compare-models`.

`comparison.txt` contains Hit@1/3/5, MRR, misses, per-case ranks, and informational indexing/benchmark runtimes for each model. Lower rank and higher Hit@K/MRR are better; runtime is reported only to make the quality/cost trade-off visible.

Custom models can be supplied by repeating `--model`:

```powershell
family-kb compare-models `
  --model intfloat/multilingual-e5-small `
  --model intfloat/multilingual-e5-base
```

Useful options:

```powershell
family-kb compare-models --top-k 30
family-kb compare-models --output-dir my_model_test
```

The first run may download models that are not yet present in the local Hugging Face cache.

## Configuration

`config.example.yaml` contains:

- `kb_path` – path to the external `RODINNE_KNOWHOW`
- `qdrant_url` – local Qdrant URL
- `qdrant_collection` – collection name, default `family_kb`
- `embedding_model` – local sentence-transformers model used by normal ingest/search/benchmark
- `chunk_size` – maximum approximate chunk length in characters
- `chunk_overlap` – overlap when a long Markdown section must be split
- `top_k` – default number of interactive search results

Chunking first follows Markdown headings (`#`, `##`, `###`, ...). Long sections are then split to the configured size with overlap. Each Qdrant point uses a deterministic UUID derived from source path, section path, and chunk index, and stores payload metadata needed for later incremental indexing.

## Tests

Unit tests do not load or download the embedding model and do not require a running Qdrant:

```powershell
pytest
```

They cover Markdown section hierarchy, long-section splitting, fenced-code handling, deterministic chunk IDs, configuration parsing, benchmark case parsing, acceptable-target matching, benchmark metrics, and model-comparison report helpers.

## Intentionally out of scope

No LLM, chatbot, RAG generation, OpenAI API, web UI, REST API, file watcher, hybrid search, reranker, OCR/PDF ingestion, multimodality, permissions, or cloud deployment.
