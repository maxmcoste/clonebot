"""Clone profile management."""

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

    model_config = {"extra": "ignore"}

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
        from clonebot.prompts.loader import PromptLoader

        loader = PromptLoader(clone_dir=self.get_dir())
        traits = ", ".join(self.personality_traits) if self.personality_traits else "not specified"

        if self.knowledge_domains:
            domains_list = ", ".join(self.knowledge_domains)
            partial = loader.load_partial("domain_open")
            domain_rule = loader.render(partial, domains=domains_list).strip()
        else:
            partial = loader.load_partial("domain_closed")
            domain_rule = loader.render(partial).strip()

        template = loader.load_template("system")
        return loader.render(
            template,
            name=self.name,
            description=self.description,
            traits=traits,
            domain_rule=domain_rule,
            memories=memories,
            language=self.language,
        )
