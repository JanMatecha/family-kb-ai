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

If PowerShell activation is blocked by execution policy, use the virtual environment explicitly:

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

`benchmarks/retrieval_cases.yaml` contains the original 12-case retrieval baseline. It intentionally includes paraphrases such as `trubka + spojka` versus source text using `hadice + fitinky`.

Run the benchmark against the currently indexed Qdrant collection:

```powershell
family-kb benchmark
```

On Windows without virtual-environment activation:

```powershell
.\.venv\Scripts\family-kb.exe benchmark
```

The command searches TOP 20 by default, prints per-case rank/score and aggregate metrics, and writes a UTF-8 report to `benchmark_results.txt`.

Metrics include Hit@K, MRR, and misses at the configured search depth.

## Embedding model comparison (V1.1b)

V1.1b compares embedding models while holding the knowledge base, chunking, benchmark cases, Qdrant search settings, and retrieval logic constant.

Run:

```powershell
.\.venv\Scripts\family-kb.exe compare-models
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

It answers two questions:

1. Where does the correct chunk really rank when a TOP-20 benchmark misses it?
2. Is the failure specific to the E5 model family, or does a different multilingual sentence-embedding family behave differently?

Run:

```powershell
.\.venv\Scripts\family-kb.exe diagnose-retrieval
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

This keeps the original V1.1b benchmark reproducible while reducing the risk of optimizing the whole search stack only for one garden failure case.

Results are written to:

```text
retrieval_diagnostics/
├── benchmark_multilingual_e5_small.txt
├── benchmark_paraphrase_multilingual_minilm_l12_v2.txt
└── comparison.txt
```

For a baseline collection `family_kb`, V1.1c uses separate experiment collections such as:

```text
family_kb_diag_multilingual_e5_small
family_kb_diag_paraphrase_multilingual_minilm_l12_v2
```

The configured baseline collection is not changed.

The report includes actual per-case ranks up to TOP 100 and aggregate Hit@1/3/5/10/20/100, MRR, misses, and informational runtimes.

If the `trubka + spojka` target appears at a moderate deep rank, a later reranker experiment becomes reasonable. If it remains very deep or missed across model families, the next step should focus on the retrieval representation rather than simply increasing TOP K.

## Benchmark target matching

Benchmark targets can identify a source by exact relative path:

```yaml
source_path: "02_ZAHRADA/02_ZAHONY/SOUHRN_ZAHONU.md"
```

or, for cross-domain cases where only the stable file name matters, by path suffix:

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
pytest
```

They cover Markdown chunking, configuration, benchmark matching/metrics, deep diagnostic metrics, and model-comparison naming/report helpers.

## Intentionally out of scope

No LLM, chatbot, RAG generation, OpenAI API, web UI, REST API, file watcher, hybrid search, reranker, OCR/PDF ingestion, multimodality, permissions, or cloud deployment.
