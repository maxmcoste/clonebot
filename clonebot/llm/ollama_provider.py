"""Ollama local LLM provider."""

from typing import Iterator

import ollama

from clonebot.llm.provider import LLMProvider


class OllamaProvider(LLMProvider):
    def __init__(self, model: str = "llama3.1", base_url: str = "http://localhost:11434"):
        self._client = ollama.Client(host=base_url)
        self._model = model

    def chat(self, messages: list[dict[str, str]]) -> str:
        response = self._client.chat(model=self._model, messages=messages)
        return response.message.content or ""

    def chat_stream(self, messages: list[dict[str, str]]) -> Iterator[str]:
        stream = self._client.chat(model=self._model, messages=messages, stream=True)
        for chunk in stream:
            if chunk.message.content:
                yield chunk.message.content
