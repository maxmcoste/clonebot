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
- To ingest legacy `.doc` files (Word 97–2003), one of:
  - `antiword` — `brew install antiword` *(recommended, lightweight)*
  - `pandoc` — `brew install pandoc` *(fallback, also needs `pip install pypandoc`)*

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
| `CLONEBOT_VISION_PROVIDER` | Vision LLM provider: `openai` or `anthropic` | `openai` |
| `CLONEBOT_VISION_MODEL` | Vision model name | `gpt-4o` |
| `CLONEBOT_VIDEO_MAX_FRAMES` | Max frames to extract from videos | `5` |
| `CLONEBOT_WHISPER_MODEL` | OpenAI Whisper model for audio transcription | `whisper-1` |

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

#### Knowledge Boundaries

By default, a clone answers **only from its ingested memories**. If a question has no relevant memory, the clone will say it doesn't know rather than hallucinate an answer.

Use `--domains` to declare areas of general knowledge the clone is allowed to draw on beyond their memories — for example, their profession or a strong passion:

```bash
uv run clonebot create "Marco" \
  --description "Architect and Inter Milan supporter" \
  --traits "analytical,passionate,opinionated" \
  --language italian \
  --domains "architecture, urban design, Italian football, Inter Milan"
```

The clone will:
- Answer freely on topics within the declared domains (e.g. architectural styles, Serie A standings)
- Rely exclusively on ingested memories for everything else (personal life, opinions, relationships)
- Honestly say "I don't know / I don't remember" for questions outside both

You can add or update knowledge domains later by re-running `create` with the same name (it overwrites the profile, memories are preserved).

### Ingest Memory Data

Feed the clone text data so it has memories to draw from:

```bash
# Ingest a single file
uv run clonebot ingest Marco ./sample_chats_marco.txt

# Ingest an entire directory (all supported formats, recursive)
uv run clonebot ingest Marco ./data/marco/
```

#### Directory Ingestion

When a directory is provided, CloneBot walks it recursively, picks up every file whose extension is supported, and shows a per-file progress bar:

```
  ✓ journal_2023.txt   (12 chunks)
  ✓ trip_report.docx   (5 chunks)
  ⚠ Skipped  'notes.pdf': extension is '.pdf' but file content is OLE2 document (.doc/.xls/.ppt)
  ✓ vacation.mp4       (1 chunk)
```

Files whose content does **not** match their extension (e.g. a `.txt` file that is actually a binary Word document) are automatically detected via magic-byte inspection, skipped with a warning, and the rest of the batch continues normally.

#### Media Memories (Photos & Videos)

CloneBot can ingest photos and videos as visual memories. Images are analyzed by a vision-capable LLM and the description is stored as a searchable memory chunk. Videos get key frames extracted and analyzed, plus optional audio transcription.

```bash
# Ingest a photo with AI vision analysis and tags
uv run clonebot ingest Marco photo.jpg --tags "daughter,birthday"

# Ingest with a manual description (skip vision API)
uv run clonebot ingest Marco photo.jpg --no-vision --description "Sarah's 5th birthday party" --tags "daughter"

# Ingest a video (frames analyzed + audio transcribed)
uv run clonebot ingest Marco vacation.mp4 --tags "hawaii,vacation"
```

**Flags:**
- `--tags / -t` — comma-separated relationship or context tags (e.g. `"daughter,birthday"`)
- `--description / -d` — rich, free-form description of the media (see below)
- `--no-vision` — skip AI vision analysis (requires `--description` for media files)

#### Writing Rich Descriptions

The `--description` flag accepts any length of free-form text. Use it to capture context that a vision model cannot infer from pixels alone — location, occasion, who the people are, and what the moment meant.

This description serves two purposes:
1. It is stored **verbatim** in the memory chunk and is always retrieved as-is during chat.
2. It is passed to the vision LLM as **context**, helping it produce a richer and more accurate visual analysis (e.g. correctly identifying people by name, understanding the occasion).

```bash
# Rich contextual description for a photo
uv run clonebot ingest Marco ./photos/massimo_cena.jpg \
  --tags "amico stretto, collega" \
  --description "Foto scattata a Milano nel dicembre 2018 durante la cena di Natale \
aziendale al ristorante Trattoria da Pino in zona Navigli. Nella foto sono con Massimo, \
il mio collega più stretto dal 2015 e amico di vecchia data. Stiamo brindando alla \
chiusura di un progetto importante che avevamo portato avanti insieme per un anno. \
È una serata che ricordo con molto affetto."

# Using --no-vision when you want to store only your description (no API call)
uv run clonebot ingest Marco ./photos/massimo_cena.jpg \
  --tags "amico stretto, collega" \
  --no-vision \
  --description "Cena di Natale 2018 con Massimo a Milano. Brindisi dopo la chiusura del progetto."
```

Good things to include in a description:
- **Who** is in the photo/video and your relationship to them
- **Where** it was taken (city, venue, occasion)
- **When** (year, season, or specific event)
- **Why** it matters — the mood, what was being celebrated, a memory it triggers

**Vision providers:** Configure with `CLONEBOT_VISION_PROVIDER` (`openai` or `anthropic`) and `CLONEBOT_VISION_MODEL`. Audio transcription uses OpenAI Whisper. Video audio extraction requires `ffmpeg` (optional — gracefully skipped if not installed).

#### Supported File Formats

| Format | Extensions | Notes |
|---|---|---|
| Plain text | `.txt`, `.md` | Auto-detects chat log format (WhatsApp, generic `Name: message`) |
| JSON | `.json` | Detects structured chat exports with `sender`/`text` fields |
| CSV | `.csv` | Detects chat-like CSVs with sender/message columns |
| PDF | `.pdf` | Extracts text from all pages |
| Word (modern) | `.docx` | Extracts paragraph text via `python-docx` |
| Word (legacy) | `.doc` | Converts to text via `antiword` (preferred) or `pandoc`; requires one to be installed |
| Images | `.jpg`, `.jpeg`, `.png`, `.gif`, `.webp` | Vision AI analysis with relationship tags |
| Videos | `.mp4`, `.mov`, `.avi`, `.mkv` | Frame extraction + vision analysis + audio transcription |

> **File-type validation** — every file is inspected by its magic bytes before parsing. If the extension does not match the actual content (e.g. a `.txt` file that contains a binary PDF), the file is rejected with a clear error message. In directory mode the offending file is skipped and ingestion continues; in single-file mode an error is shown and the command exits.

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
├── prompts/            # Prompt templates (edit these to tune behaviour)
│   ├── system.md       # Main system prompt template (global default)
│   └── partials/
│       ├── domain_open.md    # Knowledge rule when --domains is set
│       └── domain_closed.md  # Knowledge rule when no domains are set
├── media/
│   ├── vision.py       # Vision LLM analysis (OpenAI / Anthropic)
│   ├── video.py        # Frame and audio extraction (OpenCV / ffmpeg)
│   └── transcribe.py   # Audio transcription (OpenAI Whisper)
├── memory/
│   ├── chunker.py      # Text and chat-aware chunking
│   ├── embeddings.py   # Embedding providers (local / OpenAI)
│   ├── ingest.py       # File parsing and ingestion pipeline
│   ├── validate.py     # Magic-byte file-type validator
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

data/clones/
└── <clone-name>/
    ├── profile.json    # Clone profile (name, traits, domains, language)
    ├── system.md       # Optional per-clone prompt override
    └── <chroma db>     # Vector store with ingested memories
```

### Writing Style Profiles

A clone can be given a **style profile** — a markdown file that describes how the real person writes across 9 linguistic dimensions (vocabulary, syntax, rhythm, slang, pragmatics, emotional tone, imagery, stylistic signatures, silences). The profile is injected into the system prompt as both structured guidelines and few-shot writing samples, instructing the LLM to replicate that voice rather than defaulting to generic assistant language.

#### Creating a style profile

Create a `style.md` file with two sections:

```markdown
# Writing Style: Marco

## Dimensions

### 1. Vocabulary
- Register: informal-technical mix; IT jargon blended with natural Italian
- Complexity: medium — precise but never pedantic
- Dominant fields: technology, work, food

### 2. Syntax
- Short to medium sentences; rarely chains long subordinates
- Frequent mid-sentence corrections: "cioè…", "nel senso…"

### 3. Rhythm
- Heavy use of "..." for trailing off or hesitation
- Fast repetitions: "sì sì", "dai dai", "no no no"

### 4. Slang / Idiolect
- "fratè" with close friends
- Italianised English verbs: "deploya", "mergere", "runnare"

### 5. Pragmatics
- Mildly assertive; ends rhetorical points with "no?"
- Irony as default deflection under pressure

### 6. Emotional Tone
- Default: pragmatic optimism; under stress: dark humour

### 7. Imagery
- Metaphors from technology and food; concrete, rarely poetic

### 8. Stylistic Signatures
- Starts explanations with "In pratica…"
- Self-corrects with "cioè…"; closes with "no?" / "capisci?"
- Present tense even when recounting past events

### 9. Silences / Omissions
- Trails off with "..." rather than stating discomfort directly
- Changes subject abruptly when topic is too personal

## Writing Samples

> Senti, in pratica il problema è che non si capisce niente della documentazione, cioè, è scritta bene... ma non dice niente di utile, capisci?

> Dai fratè, deployiamo e vediamo. Se crasha sistemiamo dopo.

> L'ho visto, sì. Era lì. Basta.

> In pratica ho digerito la cosa, però... non so, ci vuole tempo.
```

#### Installing and inspecting a style profile

```bash
# Install a style profile for a clone
uv run clonebot style Marco ./my_style.md

# Show the currently installed style profile
uv run clonebot style Marco
```

The profile is stored at `data/clones/<name>/style.md`. When present, it is automatically loaded at chat time — no other configuration needed. The `stats` and `chat` commands show whether a style profile is active.

The 9 dimensions are documented in `lessico/struttura.rtf` and `lessico/Lessico.proposal.txt`.

### Customising Prompts

To tune behaviour for **all clones** edit the files in `clonebot/prompts/`:
- `system.md` — the main template; available variables: `{name}`, `{description}`, `{traits}`, `{domain_rule}`, `{memories}`, `{language}`
- `partials/domain_open.md` — injected as `{domain_rule}` when `--domains` is configured; also has `{domains}`
- `partials/domain_closed.md` — injected as `{domain_rule}` when no domains are set

To override the prompt for a **single clone**, drop a `system.md` file inside its data directory (`data/clones/<name>/system.md`). It takes precedence over the global default while partials remain shared.

## License

See [LICENSE](LICENSE) for details.
