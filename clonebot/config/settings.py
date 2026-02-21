"""Application configuration."""

from pathlib import Path

from pydantic import Field
from pydantic.aliases import AliasChoices
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

    # API Keys — read from unprefixed env vars (e.g. OPENAI_API_KEY) with
    # CLONEBOT_-prefixed names as fallback.
    openai_api_key: str = Field(
        default="",
        validation_alias=AliasChoices("OPENAI_API_KEY", "CLONEBOT_OPENAI_API_KEY"),
    )
    anthropic_api_key: str = Field(
        default="",
        validation_alias=AliasChoices("ANTHROPIC_API_KEY", "CLONEBOT_ANTHROPIC_API_KEY"),
    )
    ollama_base_url: str = Field(
        default="http://localhost:11434",
        validation_alias=AliasChoices("OLLAMA_BASE_URL", "CLONEBOT_OLLAMA_BASE_URL"),
    )


def get_settings() -> Settings:
    return Settings()
