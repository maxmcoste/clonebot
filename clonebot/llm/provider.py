"""Abstract LLM provider interface."""

from abc import ABC, abstractmethod
from typing import Iterator

from clonebot.config.settings import get_settings


class LLMProvider(ABC):
    @abstractmethod
    def chat(self, messages: list[dict[str, str]]) -> str:
        ...

    @abstractmethod
    def chat_stream(self, messages: list[dict[str, str]]) -> Iterator[str]:
        ...


def get_llm_provider() -> LLMProvider:
    settings = get_settings()
    provider = settings.llm_provider.lower()

    if provider == "openai":
        from clonebot.llm.openai_provider import OpenAIProvider
        return OpenAIProvider(model=settings.llm_model)
    elif provider == "anthropic":
        from clonebot.llm.anthropic_provider import AnthropicProvider
        return AnthropicProvider(model=settings.llm_model)
    elif provider == "ollama":
        from clonebot.llm.ollama_provider import OllamaProvider
        return OllamaProvider(model=settings.llm_model, base_url=settings.ollama_base_url)
    else:
        raise ValueError(f"Unknown LLM provider: {provider}")
