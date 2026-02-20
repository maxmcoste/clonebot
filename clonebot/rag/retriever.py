"""Memory retrieval with relevance scoring."""

from dataclasses import dataclass

from clonebot.memory.store import VectorStore
from clonebot.config.settings import get_settings


@dataclass
class RetrievedMemory:
    text: str
    score: float
    metadata: dict[str, str]


class Retriever:
    def __init__(self, store: VectorStore, top_k: int | None = None):
        self._store = store
        settings = get_settings()
        self._top_k = top_k or settings.retrieval_top_k

    def retrieve(self, query: str) -> list[RetrievedMemory]:
        if self._store.count() == 0:
            return []

        results = self._store.search(query, n_results=self._top_k)
        memories = []
        for doc in results:
            # ChromaDB returns cosine distance; convert to similarity
            distance = doc.get("distance", 1.0)
            score = 1.0 - distance if distance is not None else 0.0
            memories.append(RetrievedMemory(
                text=doc["text"],
                score=score,
                metadata=doc.get("metadata", {}),
            ))
        return memories
