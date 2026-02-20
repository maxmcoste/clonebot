"""Chat session management."""

from dataclasses import dataclass, field

from clonebot.core.clone import CloneProfile
from clonebot.llm.provider import LLMProvider
from clonebot.memory.store import VectorStore
from clonebot.rag.retriever import Retriever
from clonebot.rag.prompt import build_prompt


@dataclass
class ChatSession:
    clone: CloneProfile
    llm: LLMProvider
    store: VectorStore
    retriever: Retriever
    history: list[dict[str, str]] = field(default_factory=list)
    max_history: int = 20

    def chat(self, user_message: str) -> str:
        relevant_memories = self.retriever.retrieve(user_message)
        system_prompt = build_prompt(self.clone, relevant_memories)

        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(self.history[-self.max_history :])
        messages.append({"role": "user", "content": user_message})

        response = self.llm.chat(messages)

        self.history.append({"role": "user", "content": user_message})
        self.history.append({"role": "assistant", "content": response})

        return response

    def chat_stream(self, user_message: str):
        relevant_memories = self.retriever.retrieve(user_message)
        system_prompt = build_prompt(self.clone, relevant_memories)

        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(self.history[-self.max_history :])
        messages.append({"role": "user", "content": user_message})

        full_response = ""
        for chunk in self.llm.chat_stream(messages):
            full_response += chunk
            yield chunk

        self.history.append({"role": "user", "content": user_message})
        self.history.append({"role": "assistant", "content": full_response})
