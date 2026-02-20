"""Smart text chunking with metadata."""

from dataclasses import dataclass, field


@dataclass
class Chunk:
    text: str
    metadata: dict[str, str] = field(default_factory=dict)


def chunk_text(
    text: str,
    chunk_size: int = 500,
    overlap: int = 50,
    metadata: dict[str, str] | None = None,
) -> list[Chunk]:
    """Split text into chunks by paragraphs, respecting boundaries."""
    if not text.strip():
        return []

    base_meta = metadata or {}
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]

    chunks: list[Chunk] = []
    current = ""
    current_words = 0

    for para in paragraphs:
        para_words = len(para.split())

        # If a single paragraph exceeds chunk_size, split it by sentences
        if para_words > chunk_size:
            if current:
                chunks.append(Chunk(text=current.strip(), metadata={**base_meta}))
                current = ""
                current_words = 0
            chunks.extend(_split_long_text(para, chunk_size, overlap, base_meta))
            continue

        if current_words + para_words > chunk_size and current:
            chunks.append(Chunk(text=current.strip(), metadata={**base_meta}))
            # Keep overlap from end of current chunk
            overlap_text = " ".join(current.split()[-overlap:]) if overlap > 0 else ""
            current = overlap_text + "\n\n" + para if overlap_text else para
            current_words = len(current.split())
        else:
            current = current + "\n\n" + para if current else para
            current_words += para_words

    if current.strip():
        chunks.append(Chunk(text=current.strip(), metadata={**base_meta}))

    # Add chunk index to metadata
    for i, chunk in enumerate(chunks):
        chunk.metadata["chunk_index"] = str(i)

    return chunks


def chunk_chat_messages(
    messages: list[dict[str, str]],
    chunk_size: int = 500,
    metadata: dict[str, str] | None = None,
) -> list[Chunk]:
    """Chunk chat messages, respecting conversation boundaries."""
    if not messages:
        return []

    base_meta = metadata or {}
    chunks: list[Chunk] = []
    current_lines: list[str] = []
    current_words = 0

    for msg in messages:
        speaker = msg.get("speaker", "Unknown")
        text = msg.get("text", "")
        timestamp = msg.get("timestamp", "")

        line = f"[{timestamp}] {speaker}: {text}" if timestamp else f"{speaker}: {text}"
        line_words = len(line.split())

        if current_words + line_words > chunk_size and current_lines:
            chunks.append(Chunk(
                text="\n".join(current_lines),
                metadata={**base_meta, "type": "chat"},
            ))
            current_lines = []
            current_words = 0

        current_lines.append(line)
        current_words += line_words

    if current_lines:
        chunks.append(Chunk(
            text="\n".join(current_lines),
            metadata={**base_meta, "type": "chat"},
        ))

    for i, chunk in enumerate(chunks):
        chunk.metadata["chunk_index"] = str(i)

    return chunks


def _split_long_text(
    text: str, chunk_size: int, overlap: int, base_meta: dict[str, str]
) -> list[Chunk]:
    """Split a long text block by word count."""
    words = text.split()
    chunks: list[Chunk] = []
    start = 0

    while start < len(words):
        end = start + chunk_size
        chunk_text = " ".join(words[start:end])
        chunks.append(Chunk(text=chunk_text, metadata={**base_meta}))
        start = end - overlap if overlap > 0 else end

    return chunks
