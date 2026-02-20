"""System prompt builder."""

from clonebot.core.clone import CloneProfile
from clonebot.rag.retriever import RetrievedMemory


def build_prompt(clone: CloneProfile, memories: list[RetrievedMemory]) -> str:
    """Build system prompt combining persona and retrieved memories."""
    if memories:
        memory_texts = []
        for i, mem in enumerate(memories, 1):
            source = mem.metadata.get("source", "unknown")
            memory_texts.append(f"[Memory {i} (from {source})]:\n{mem.text}")
        memories_str = "\n\n".join(memory_texts)
    else:
        memories_str = "(No relevant memories found for this conversation.)"

    return clone.build_system_prompt(memories_str)
