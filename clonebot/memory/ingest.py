"""Data ingestion pipeline."""

import csv
import io
import json
import re
import shutil
from pathlib import Path

from clonebot.memory.chunker import Chunk, chunk_text, chunk_chat_messages
from clonebot.config.settings import get_settings

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv"}
TEXT_EXTENSIONS = {".txt", ".md", ".json", ".pdf", ".csv", ".docx", ".doc"}


def ingest_file(
    file_path: Path,
    tags: list[str] | None = None,
    description: str = "",
    use_vision: bool = True,
) -> list[Chunk]:
    """Ingest a single file and return chunks.

    Raises
    ------
    FileTypeMismatchError
        If the file's content does not match its declared extension.
    ValueError
        If the file extension is not supported.
    """
    from clonebot.memory.validate import validate_file_type
    validate_file_type(file_path)

    suffix = file_path.suffix.lower()
    meta = {"source": file_path.name, "source_path": str(file_path)}

    if suffix in IMAGE_EXTENSIONS:
        return _ingest_image(file_path, meta, tags=tags, description=description, use_vision=use_vision)
    elif suffix in VIDEO_EXTENSIONS:
        return _ingest_video(file_path, meta, tags=tags, description=description, use_vision=use_vision)
    elif suffix in (".txt", ".md"):
        return _ingest_text(file_path, meta)
    elif suffix == ".json":
        return _ingest_json(file_path, meta)
    elif suffix == ".pdf":
        return _ingest_pdf(file_path, meta)
    elif suffix == ".csv":
        return _ingest_csv(file_path, meta)
    elif suffix == ".docx":
        return _ingest_docx(file_path, meta)
    elif suffix == ".doc":
        return _ingest_doc(file_path, meta)
    else:
        raise ValueError(f"Unsupported file type: {suffix}")


def ingest_directory(
    dir_path: Path,
    tags: list[str] | None = None,
    description: str = "",
    use_vision: bool = True,
) -> tuple[list[Chunk], list[tuple[Path, str]]]:
    """Ingest all supported files in a directory.

    Each file is validated (magic bytes vs. extension) before ingestion.
    Files that fail validation or raise any other error are skipped and their
    path + reason are collected in the returned error list so the caller can
    report them without aborting the whole batch.

    Returns
    -------
    chunks : list[Chunk]
        All successfully ingested chunks.
    errors : list[tuple[Path, str]]
        One entry per skipped file: (file_path, human-readable reason).
    """
    supported = TEXT_EXTENSIONS | IMAGE_EXTENSIONS | VIDEO_EXTENSIONS
    all_chunks: list[Chunk] = []
    errors: list[tuple[Path, str]] = []

    for f in sorted(dir_path.rglob("*")):
        if not (f.is_file() and f.suffix.lower() in supported):
            continue
        try:
            all_chunks.extend(
                ingest_file(f, tags=tags, description=description, use_vision=use_vision)
            )
        except Exception as e:
            errors.append((f, str(e)))

    return all_chunks, errors


def _build_media_text(
    media_type: str,
    filename: str,
    tags: list[str] | None,
    description: str,
    analysis: str,
) -> str:
    """Compose chunk text with header, tags, description, and analysis."""
    parts = [f"[{media_type} memory: {filename}]"]

    if tags:
        parts.append(f"Tags: {', '.join(tags)}")

    if description:
        parts.append(f"Description: {description}")

    if analysis:
        parts.append(f"\n{analysis}")

    return "\n".join(parts)


def _ingest_image(
    path: Path,
    meta: dict[str, str],
    tags: list[str] | None = None,
    description: str = "",
    use_vision: bool = True,
) -> list[Chunk]:
    """Ingest a photo, optionally using vision AI for analysis."""
    meta["format"] = "photo"
    if tags:
        meta["tags"] = ",".join(tags)

    analysis = ""
    if use_vision:
        from clonebot.media.vision import get_vision_analyzer
        analyzer = get_vision_analyzer()
        context = description or ""
        if tags:
            context = f"{context} (people/tags: {', '.join(tags)})".strip()
        analysis = analyzer.describe_image(path, context=context)

    text = _build_media_text("Photo", path.name, tags, description, analysis)
    return [Chunk(text=text, metadata={**meta, "chunk_index": "0"})]


def _ingest_video(
    path: Path,
    meta: dict[str, str],
    tags: list[str] | None = None,
    description: str = "",
    use_vision: bool = True,
) -> list[Chunk]:
    """Ingest a video: extract frames for vision analysis and audio for transcription."""
    meta["format"] = "video"
    if tags:
        meta["tags"] = ",".join(tags)

    frame_descriptions: list[str] = []
    transcript = ""
    temp_dirs: list[Path] = []

    # Extract and analyze frames
    if use_vision:
        from clonebot.media.video import extract_frames
        from clonebot.media.vision import get_vision_analyzer

        frames = extract_frames(path)
        if frames and frames[0].parent.exists():
            temp_dirs.append(frames[0].parent)

        analyzer = get_vision_analyzer()
        context = description or ""
        if tags:
            context = f"{context} (people/tags: {', '.join(tags)})".strip()

        for i, frame_path in enumerate(frames):
            desc = analyzer.describe_image(frame_path, context=f"Frame {i + 1} of video. {context}")
            frame_descriptions.append(f"[Frame {i + 1}] {desc}")

    # Extract and transcribe audio
    from clonebot.media.video import extract_audio
    audio_path = extract_audio(path)
    if audio_path:
        if audio_path.parent.exists():
            temp_dirs.append(audio_path.parent)
        from clonebot.media.transcribe import transcribe_audio
        transcript = transcribe_audio(audio_path)

    # Build combined analysis
    analysis_parts = []
    if frame_descriptions:
        analysis_parts.append("Visual analysis:\n" + "\n".join(frame_descriptions))
    if transcript:
        analysis_parts.append(f"Audio transcript:\n{transcript}")

    analysis = "\n\n".join(analysis_parts)
    text = _build_media_text("Video", path.name, tags, description, analysis)

    # Clean up temp directories
    for d in temp_dirs:
        shutil.rmtree(d, ignore_errors=True)

    chunks = [Chunk(text=text, metadata={**meta, "chunk_index": "0"})]

    # If text is very long, split into additional chunks
    settings = get_settings()
    if len(text.split()) > settings.chunk_size:
        chunks = chunk_text(text, chunk_size=settings.chunk_size, overlap=settings.chunk_overlap, metadata=meta)
        for c in chunks:
            c.metadata["format"] = "video"
            if tags:
                c.metadata["tags"] = ",".join(tags)

    return chunks


def _ingest_text(path: Path, meta: dict[str, str]) -> list[Chunk]:
    text = path.read_text(encoding="utf-8", errors="replace")

    # Detect if this looks like a chat log
    chat_messages = _detect_chat_format(text)
    if chat_messages:
        meta["format"] = "chat"
        settings = get_settings()
        return chunk_chat_messages(chat_messages, chunk_size=settings.chunk_size, metadata=meta)

    settings = get_settings()
    return chunk_text(text, chunk_size=settings.chunk_size, overlap=settings.chunk_overlap, metadata=meta)


def _ingest_json(path: Path, meta: dict[str, str]) -> list[Chunk]:
    data = json.loads(path.read_text(encoding="utf-8"))
    settings = get_settings()

    # If it's a list of messages, treat as chat
    if isinstance(data, list) and data and isinstance(data[0], dict):
        if any(k in data[0] for k in ("text", "message", "content")):
            messages = []
            for item in data:
                messages.append({
                    "speaker": item.get("sender", item.get("from", item.get("speaker", "Unknown"))),
                    "text": item.get("text", item.get("message", item.get("content", ""))),
                    "timestamp": item.get("timestamp", item.get("date", "")),
                })
            meta["format"] = "chat_json"
            return chunk_chat_messages(messages, chunk_size=settings.chunk_size, metadata=meta)

    # Otherwise treat as plain text
    text = json.dumps(data, indent=2, ensure_ascii=False)
    return chunk_text(text, chunk_size=settings.chunk_size, overlap=settings.chunk_overlap, metadata=meta)


def _ingest_pdf(path: Path, meta: dict[str, str]) -> list[Chunk]:
    import pymupdf

    doc = pymupdf.open(str(path))
    pages: list[str] = []
    for page in doc:
        pages.append(page.get_text())
    doc.close()

    text = "\n\n".join(pages)
    meta["format"] = "pdf"
    settings = get_settings()
    return chunk_text(text, chunk_size=settings.chunk_size, overlap=settings.chunk_overlap, metadata=meta)


def _ingest_csv(path: Path, meta: dict[str, str]) -> list[Chunk]:
    """Ingest CSV, attempting chat export detection."""
    text = path.read_text(encoding="utf-8", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    rows = list(reader)

    if not rows:
        return []

    settings = get_settings()
    fields = set(rows[0].keys())

    # Detect chat-like CSV
    chat_fields = {"sender", "from", "author", "speaker", "user"}
    msg_fields = {"text", "message", "content", "body"}
    if fields & chat_fields and fields & msg_fields:
        sender_key = next(k for k in fields if k in chat_fields)
        msg_key = next(k for k in fields if k in msg_fields)
        time_fields = {"timestamp", "date", "time", "datetime"}
        time_key = next((k for k in fields if k in time_fields), None)

        messages = []
        for row in rows:
            messages.append({
                "speaker": row[sender_key],
                "text": row[msg_key],
                "timestamp": row.get(time_key, "") if time_key else "",
            })
        meta["format"] = "chat_csv"
        return chunk_chat_messages(messages, chunk_size=settings.chunk_size, metadata=meta)

    # Plain CSV: concatenate rows
    lines = []
    for row in rows:
        lines.append(" | ".join(f"{k}: {v}" for k, v in row.items()))
    text = "\n".join(lines)
    return chunk_text(text, chunk_size=settings.chunk_size, overlap=settings.chunk_overlap, metadata=meta)


def _ingest_docx(path: Path, meta: dict[str, str]) -> list[Chunk]:
    from docx import Document

    doc = Document(str(path))
    paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
    text = "\n\n".join(paragraphs)
    meta["format"] = "docx"
    settings = get_settings()
    return chunk_text(text, chunk_size=settings.chunk_size, overlap=settings.chunk_overlap, metadata=meta)


def _ingest_doc(path: Path, meta: dict[str, str]) -> list[Chunk]:
    """Ingest a legacy .doc file by converting to plain text.

    Tries converters in order:
    1. antiword   — brew install antiword
    2. pypandoc   — pip install pypandoc + brew install pandoc
    """
    text = _convert_doc_to_text(path)
    meta["format"] = "doc"
    settings = get_settings()
    return chunk_text(text, chunk_size=settings.chunk_size, overlap=settings.chunk_overlap, metadata=meta)


def _convert_doc_to_text(path: Path) -> str:
    """Convert a legacy .doc file to plain text using available system tools."""
    import subprocess

    # 1. Try antiword (fast, lightweight: brew install antiword)
    if shutil.which("antiword"):
        result = subprocess.run(
            ["antiword", str(path)],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout

    # 2. Try pypandoc (requires pandoc: brew install pandoc)
    try:
        import pypandoc
        return pypandoc.convert_file(str(path), "plain", format="doc")
    except Exception:
        pass

    raise RuntimeError(
        f"Cannot read '{path.name}': no legacy .doc converter found.\n"
        "Install one of:\n"
        "  • antiword:  brew install antiword\n"
        "  • pandoc:    brew install pandoc  (and pip install pypandoc)"
    )


# WhatsApp format: "1/2/24, 12:34 - Name: message"
_WHATSAPP_RE = re.compile(r"^\d{1,2}/\d{1,2}/\d{2,4},?\s+\d{1,2}:\d{2}\s*(?:AM|PM|am|pm)?\s*-\s+(.+?):\s+(.+)")
# Generic chat: "Name: message" or "[timestamp] Name: message"
_GENERIC_CHAT_RE = re.compile(r"^(?:\[([^\]]+)\]\s+)?([^:]{1,40}):\s+(.+)")


def _detect_chat_format(text: str) -> list[dict[str, str]] | None:
    """Try to detect if text is a chat log."""
    lines = text.strip().split("\n")
    if len(lines) < 3:
        return None

    messages: list[dict[str, str]] = []
    match_count = 0

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Try WhatsApp format
        m = _WHATSAPP_RE.match(line)
        if m:
            messages.append({"speaker": m.group(1), "text": m.group(2)})
            match_count += 1
            continue

        # Try generic chat format
        m = _GENERIC_CHAT_RE.match(line)
        if m:
            messages.append({
                "timestamp": m.group(1) or "",
                "speaker": m.group(2),
                "text": m.group(3),
            })
            match_count += 1
            continue

    # Consider it a chat if >50% of lines match
    if match_count > len(lines) * 0.5:
        return messages
    return None
