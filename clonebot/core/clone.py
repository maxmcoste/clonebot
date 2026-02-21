"""Clone profile management."""

import json
from pathlib import Path

from pydantic import BaseModel, Field

from clonebot.config.settings import get_settings


SUPPORTED_LANGUAGES = {"english", "italian"}


class CloneProfile(BaseModel):
    name: str
    description: str = ""
    language: str = "english"
    personality_traits: list[str] = Field(default_factory=list)
    knowledge_domains: list[str] = Field(default_factory=list)
    system_prompt_template: str = (
        "You are {name}. {description}\n"
        "Your personality traits include: {traits}.\n\n"
        "KNOWLEDGE BOUNDARIES — follow these rules strictly:\n"
        "1. Your memories (provided below) are your sole source of personal knowledge: "
        "events, opinions, relationships, experiences, and facts about your life. "
        "Do not invent or extrapolate anything beyond them.\n"
        "2. {domain_rule}\n"
        "3. When asked about something not covered by your memories and outside your "
        "knowledge domains, honestly say you don't know or don't remember. "
        "Never fabricate answers.\n\n"
        "Here are your memories relevant to this conversation:\n\n"
        "{memories}\n\n"
        "Respond as {name} would, in first person, staying true to their personality and memories.\n"
        "IMPORTANT: You MUST always respond in {language}."
    )

    def get_dir(self) -> Path:
        settings = get_settings()
        clone_dir = settings.data_dir / self.name.lower().replace(" ", "_")
        return clone_dir

    def save(self) -> Path:
        clone_dir = self.get_dir()
        clone_dir.mkdir(parents=True, exist_ok=True)
        (clone_dir / "raw").mkdir(exist_ok=True)

        profile_path = clone_dir / "profile.json"
        profile_path.write_text(self.model_dump_json(indent=2))
        return profile_path

    @classmethod
    def load(cls, name: str) -> "CloneProfile":
        settings = get_settings()
        clone_dir = settings.data_dir / name.lower().replace(" ", "_")
        profile_path = clone_dir / "profile.json"
        if not profile_path.exists():
            raise FileNotFoundError(f"Clone '{name}' not found at {profile_path}")
        return cls.model_validate_json(profile_path.read_text())

    @classmethod
    def list_all(cls) -> list["CloneProfile"]:
        settings = get_settings()
        clones = []
        if not settings.data_dir.exists():
            return clones
        for d in sorted(settings.data_dir.iterdir()):
            profile_path = d / "profile.json"
            if profile_path.exists():
                clones.append(cls.model_validate_json(profile_path.read_text()))
        return clones

    def build_system_prompt(self, memories: str) -> str:
        traits = ", ".join(self.personality_traits) if self.personality_traits else "not specified"
        if self.knowledge_domains:
            domains_list = ", ".join(self.knowledge_domains)
            domain_rule = (
                f"Beyond your personal memories, you may draw on your general knowledge "
                f"in these areas: {domains_list}. "
                f"For all other topics, rely only on your memories."
            )
        else:
            domain_rule = (
                "You have no general knowledge domains beyond your memories. "
                "Politely decline any question you cannot answer from them."
            )
        return self.system_prompt_template.format(
            name=self.name,
            description=self.description,
            traits=traits,
            domain_rule=domain_rule,
            memories=memories,
            language=self.language,
        )
