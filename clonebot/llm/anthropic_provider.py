"""Anthropic Claude LLM provider."""

from typing import Iterator

import anthropic

from clonebot.llm.provider import LLMProvider


class AnthropicProvider(LLMProvider):
    def __init__(self, model: str = "claude-sonnet-4-5-20250929"):
        self._client = anthropic.Anthropic()
        self._model = model

    def chat(self, messages: list[dict[str, str]]) -> str:
        # Anthropic uses system as a separate param
        system = ""
        chat_messages = []
        for msg in messages:
            if msg["role"] == "system":
                system = msg["content"]
            else:
                chat_messages.append(msg)

        response = self._client.messages.create(
            model=self._model,
            max_tokens=4096,
            system=system,
            messages=chat_messages,
        )
        return response.content[0].text

    def chat_stream(self, messages: list[dict[str, str]]) -> Iterator[str]:
        system = ""
        chat_messages = []
        for msg in messages:
            if msg["role"] == "system":
                system = msg["content"]
            else:
                chat_messages.append(msg)

        with self._client.messages.stream(
            model=self._model,
            max_tokens=4096,
            system=system,
            messages=chat_messages,
        ) as stream:
            for text in stream.text_stream:
                yield text
