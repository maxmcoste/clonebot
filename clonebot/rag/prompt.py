"""System prompt builder."""

from clonebot.core.clone import CloneProfile
from clonebot.rag.retriever import RetrievedMemory


def build_prompt(clone: CloneProfile, memories: list[RetrievedMemory]) -> str:
    """Build system prompt combining persona and retrieved memories."""
    if memories:
        memory_texts = []
        for i, mem in enumerate(memories, 1):
            source = mem.metadata.get("source", "unknown")
            fmt = mem.metadata.get("format", "")
            tags_str = mem.metadata.get("tags", "")

            if fmt == "photo":
                label = f"[Memory {i} (photo — from {source}"
                if tags_str:
                    label += f" — tagged: {tags_str}"
                label += ")]"
            elif fmt == "video":
                label = f"[Memory {i} (video — from {source}"
                if tags_str:
                    label += f" — tagged: {tags_str}"
                label += ")]"
            else:
                label = f"[Memory {i} (from {source})]"

            memory_texts.append(f"{label}:\n{mem.text}")
        memories_str = "\n\n".join(memory_texts)
    else:
        memories_str = "(No relevant memories found for this conversation.)"

    return clone.build_system_prompt(memories_str)
