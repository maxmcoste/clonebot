# CloneBot

CloneBot is a CLI application that creates digital clones of people you can chat with. Feed it chat logs, documents, or any text data from a person, and CloneBot builds a memory-augmented conversational agent that responds in their voice and style.

It uses Retrieval-Augmented Generation (RAG) to ground every response in real memories ingested from source material, combined with a personality profile you define.

## How It Works

1. **Create a clone** with a name, description, personality traits, and language.
2. **Ingest data** — chat exports, documents, notes — to build the clone's memory.
3. **Chat** — CloneBot retrieves the most relevant memories for each message and prompts the LLM to respond as that person.

### Architecture

```
User message
  │
  ▼
Retriever ──► Vector Store (ChromaDB) ──► Top-K relevant memory chunks
  │
  ▼
Prompt Builder ──► System prompt with persona + retrieved memories
  │
  ▼
LLM Provider (OpenAI / Anthropic / Ollama) ──► Streamed response
```

- **Memory ingestion** — Files are parsed, split into overlapping chunks (paragraph-aware for prose, conversation-boundary-aware for chats), embedded, and stored in a per-clone ChromaDB vector database.
- **Retrieval** — At chat time, the user's message is embedded and the top-K most similar chunks are retrieved using cosine similarity.
- **Prompt construction** — A system prompt is built from the clone's profile (name, description, traits, language) plus the retrieved memories, instructing the LLM to respond as that person.
- **Streaming** — Responses are streamed token-by-token to the terminal with rich formatting.

## Requirements

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) package manager

## Installation

```bash
# Clone the repository
git clone <repo-url>
cd CloneBot

# Install dependencies
uv sync
```

## Configuration

Copy the example environment file and fill in your API keys:

```bash
cp .env.example .env
```

### Environment Variables

| Variable | Description | Default |
|---|---|---|
| `CLONEBOT_LLM_PROVIDER` | LLM provider: `openai`, `anthropic`, or `ollama` | `openai` |
| `CLONEBOT_LLM_MODEL` | Model name (e.g. `gpt-4o`, `claude-sonnet-4-5-20250929`) | `gpt-4o` |
| `CLONEBOT_EMBEDDING_PROVIDER` | Embedding provider: `local` or `openai` | `local` |
| `CLONEBOT_EMBEDDING_MODEL` | Local embedding model | `all-MiniLM-L6-v2` |
| `OPENAI_API_KEY` | OpenAI API key (if using OpenAI provider) | — |
| `ANTHROPIC_API_KEY` | Anthropic API key (if using Anthropic provider) | — |
| `OLLAMA_BASE_URL` | Ollama server URL (if using Ollama provider) | `http://localhost:11434` |

The `local` embedding provider uses [sentence-transformers](https://www.sbert.net/) and runs entirely on your machine with no API key required.

## Usage

All commands are run via `uv run clonebot`.

### Create a Clone

```bash
uv run clonebot create "Marco" \
  --description "My Italian friend who loves cooking and philosophy" \
  --traits "funny,sarcastic,warm,opinionated" \
  --language italian
```

Supported languages: `english`, `italian`.

### Ingest Memory Data

Feed the clone text data so it has memories to draw from:

```bash
# Ingest a single file
uv run clonebot ingest Marco ./sample_chats_marco.txt

# Ingest an entire directory
uv run clonebot ingest Marco ./data/marco/
```

#### Supported File Formats

| Format | Extensions | Notes |
|---|---|---|
| Plain text | `.txt`, `.md` | Auto-detects chat log format (WhatsApp, generic `Name: message`) |
| JSON | `.json` | Detects structured chat exports with `sender`/`text` fields |
| CSV | `.csv` | Detects chat-like CSVs with sender/message columns |
| PDF | `.pdf` | Extracts text from all pages |
| Word | `.docx` | Extracts paragraph text |

### List Clones

```bash
uv run clonebot list
```

### View Clone Stats

```bash
uv run clonebot stats Marco
```

Shows the number of memory chunks, database path, language, and profile details.

### Chat

```bash
uv run clonebot chat Marco
```

Override the LLM provider or model for a session:

```bash
uv run clonebot chat Marco --provider anthropic --model claude-sonnet-4-5-20250929
```

Type `quit`, `exit`, or `q` to end the session.

## Project Structure

```
clonebot/
├── cli.py              # Typer CLI commands
├── config/
│   └── settings.py     # Pydantic Settings (env-driven configuration)
├── core/
│   ├── clone.py        # Clone profile model (create, save, load)
│   └── session.py      # Chat session with history management
├── memory/
│   ├── chunker.py      # Text and chat-aware chunking
│   ├── embeddings.py   # Embedding providers (local / OpenAI)
│   ├── ingest.py       # File parsing and ingestion pipeline
│   └── store.py        # ChromaDB vector store
├── rag/
│   ├── prompt.py       # System prompt builder
│   └── retriever.py    # Similarity search and memory retrieval
├── llm/
│   ├── provider.py     # Abstract LLM interface and factory
│   ├── openai_provider.py
│   ├── anthropic_provider.py
│   └── ollama_provider.py
├── voice/              # (planned)
├── style/              # (planned)
└── avatar/             # (planned)
```

## License

See [LICENSE](LICENSE) for details.
