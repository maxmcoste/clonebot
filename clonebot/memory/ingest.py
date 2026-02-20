"""Data ingestion pipeline."""

import csv
import io
import json
import re
from pathlib import Path

from clonebot.memory.chunker import Chunk, chunk_text, chunk_chat_messages
from clonebot.config.settings import get_settings


def ingest_file(file_path: Path) -> list[Chunk]:
    """Ingest a single file and return chunks."""
    suffix = file_path.suffix.lower()
    meta = {"source": file_path.name, "source_path": str(file_path)}

    if suffix in (".txt", ".md"):
        return _ingest_text(file_path, meta)
    elif suffix == ".json":
        return _ingest_json(file_path, meta)
    elif suffix == ".pdf":
        return _ingest_pdf(file_path, meta)
    elif suffix == ".csv":
        return _ingest_csv(file_path, meta)
    elif suffix == ".docx":
        return _ingest_docx(file_path, meta)
    else:
        raise ValueError(f"Unsupported file type: {suffix}")


def ingest_directory(dir_path: Path) -> list[Chunk]:
    """Ingest all supported files in a directory."""
    supported = {".txt", ".md", ".json", ".pdf", ".csv", ".docx"}
    all_chunks: list[Chunk] = []

    for f in sorted(dir_path.rglob("*")):
        if f.is_file() and f.suffix.lower() in supported:
            all_chunks.extend(ingest_file(f))

    return all_chunks


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
