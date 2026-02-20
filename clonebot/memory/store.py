"""Vector store interface using ChromaDB."""

from pathlib import Path

import chromadb

from clonebot.memory.chunker import Chunk
from clonebot.memory.embeddings import EmbeddingProvider


class VectorStore:
    def __init__(self, clone_dir: Path, embedding_provider: EmbeddingProvider):
        self._db_path = clone_dir / "chroma_db"
        self._db_path.mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(path=str(self._db_path))
        self._collection = self._client.get_or_create_collection(
            name="memories",
            metadata={"hnsw:space": "cosine"},
        )
        self._embedder = embedding_provider

    def add_documents(self, chunks: list[Chunk]) -> int:
        if not chunks:
            return 0

        texts = [c.text for c in chunks]
        metadatas = [c.metadata for c in chunks]
        embeddings = self._embedder.embed(texts)

        # Generate unique IDs based on current count
        start_id = self._collection.count()
        ids = [f"doc_{start_id + i}" for i in range(len(chunks))]

        self._collection.add(
            ids=ids,
            documents=texts,
            embeddings=embeddings,
            metadatas=metadatas,
        )
        return len(chunks)

    def search(
        self,
        query: str,
        n_results: int = 5,
        where: dict | None = None,
    ) -> list[dict]:
        query_embedding = self._embedder.embed([query])[0]

        kwargs = {
            "query_embeddings": [query_embedding],
            "n_results": min(n_results, self._collection.count() or 1),
        }
        if where:
            kwargs["where"] = where

        results = self._collection.query(**kwargs)

        documents = []
        for i in range(len(results["ids"][0])):
            documents.append({
                "id": results["ids"][0][i],
                "text": results["documents"][0][i],
                "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                "distance": results["distances"][0][i] if results["distances"] else None,
            })
        return documents

    def count(self) -> int:
        return self._collection.count()

    def stats(self) -> dict:
        count = self._collection.count()
        return {
            "total_chunks": count,
            "db_path": str(self._db_path),
        }
