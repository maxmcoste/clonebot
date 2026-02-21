"""Prompt template loader and renderer."""

from pathlib import Path

_PROMPTS_DIR = Path(__file__).parent


class PromptLoader:
    """Loads and renders prompt templates from markdown files.

    Resolution order for templates:
    1. Per-clone override  — <clone_dir>/system.md  (if clone_dir is given)
    2. Global default      — clonebot/prompts/system.md

    Partials (domain_open.md, domain_closed.md) are always loaded from
    clonebot/prompts/partials/ with no per-clone override.
    """

    def __init__(self, clone_dir: Path | None = None):
        self._global_dir = _PROMPTS_DIR
        self._clone_dir = clone_dir

    def load_template(self, name: str = "system") -> str:
        """Return the raw template string, checking per-clone override first."""
        if self._clone_dir:
            override = self._clone_dir / f"{name}.md"
            if override.exists():
                return override.read_text(encoding="utf-8")
        return (self._global_dir / f"{name}.md").read_text(encoding="utf-8")

    def load_partial(self, name: str) -> str:
        """Return the raw partial string from the global partials directory."""
        return (self._global_dir / "partials" / f"{name}.md").read_text(encoding="utf-8")

    def render(self, template: str, **kwargs: str) -> str:
        """Render a template by substituting {variable} placeholders."""
        return template.format(**kwargs)
