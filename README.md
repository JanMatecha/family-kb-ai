# family-kb-ai

Small local POC for semantic vector search over an external Markdown family knowledge base.

The goal of V1 is deliberately narrow: verify that semantic search can find the right knowledge even when the query uses different words than the source Markdown.

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
vector search from CLI
```

**Markdown is the source of truth. Qdrant is only a rebuildable search index.** The knowledge base itself is not stored in this repository. Qdrant can be deleted and rebuilt from the Markdown files at any time.

V1 uses `intfloat/multilingual-e5-small` by default. For E5 models the embedding layer applies the recommended `passage:` and `query:` prefixes. The model is downloaded on first use and then runs locally.

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

For development/tests:

```powershell
pip install -e ".[dev]"
```

### 2. Start Qdrant

```powershell
docker compose up -d
```

Qdrant REST API is exposed only on the local machine at `http://localhost:6333`. The standard image also provides its local dashboard at `http://localhost:6333/dashboard`.

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

V1 intentionally supports only an explicit full rebuild. It recursively indexes all `*.md` files under `kb_path`.

### 5. Search

```powershell
family-kb search "jak jsme řešili hadici?"
```

Default output is TOP 5 and includes score, source path, Markdown section hierarchy, and chunk text.

Override result count:

```powershell
family-kb search "jak připojit hadici" --top-k 10
```

Optional simple category filter:

```powershell
family-kb search "jak připojit hadici" --category 02_ZAHRADA
```

## Configuration

`config.example.yaml` contains the V1 settings:

- `kb_path` – path to the external `RODINNE_KNOWHOW`
- `qdrant_url` – local Qdrant URL
- `qdrant_collection` – collection name, default `family_kb`
- `embedding_model` – local sentence-transformers model
- `chunk_size` – maximum approximate chunk length in characters
- `chunk_overlap` – overlap when a long Markdown section must be split
- `top_k` – default number of search results

Chunking first follows Markdown headings (`#`, `##`, `###`, ...). Long sections are then split to the configured size with overlap. Each Qdrant point uses a deterministic UUID derived from source path, section path, and chunk index, and stores payload metadata needed for later incremental indexing.

## Tests

Unit tests do not load or download the embedding model and do not require Qdrant:

```powershell
pytest
```

They cover Markdown section hierarchy, long-section splitting, fenced-code handling, deterministic chunk IDs, and configuration parsing.

## Intentionally out of scope for V1

No LLM, chatbot, RAG generation, OpenAI API, web UI, REST API, file watcher, hybrid search, reranker, OCR/PDF ingestion, multimodality, permissions, or cloud deployment.
