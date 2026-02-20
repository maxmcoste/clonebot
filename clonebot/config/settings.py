"""Application configuration."""

from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = {"env_prefix": "CLONEBOT_", "env_file": ".env", "extra": "ignore"}

    # Paths
    data_dir: Path = Path("data/clones")

    # LLM
    llm_provider: str = "openai"
    llm_model: str = "gpt-4o"

    # Embedding
    embedding_provider: str = "local"
    embedding_model: str = "all-MiniLM-L6-v2"
    openai_embedding_model: str = "text-embedding-3-small"

    # Vision / Media
    vision_provider: str = "openai"
    vision_model: str = "gpt-4o"
    video_max_frames: int = 5
    whisper_model: str = "whisper-1"

    # RAG
    chunk_size: int = 500
    chunk_overlap: int = 50
    retrieval_top_k: int = 5

    # API Keys (read from env without prefix)
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    ollama_base_url: str = "http://localhost:11434"


def get_settings() -> Settings:
    return Settings()
