"""Prompt template loader and renderer."""

import re
from pathlib import Path

_PROMPTS_DIR = Path(__file__).parent


class PromptLoader:
    """Loads and renders prompt templates from markdown files.

    Resolution order for templates:
    1. Per-clone override  — <clone_dir>/system.md  (if clone_dir is given)
    2. Global default      — clonebot/prompts/system.md

    Partials (domain_open.md, domain_closed.md, style_guide.md) are always
    loaded from clonebot/prompts/partials/ with no per-clone override.

    Style profiles are loaded from <clone_dir>/style.md when present.
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

    def load_style(self) -> dict[str, str] | None:
        """Parse <clone_dir>/style.md and return dimensions + samples strings.

        The style.md file is expected to have two top-level sections:
          ## Dimensions   — free-form bullet text per dimension
          ## Writing Samples — one blockquote (> …) per sample

        Returns None if no style.md exists for this clone.
        """
        if not self._clone_dir:
            return None
        style_path = self._clone_dir / "style.md"
        if not style_path.exists():
            return None

        text = style_path.read_text(encoding="utf-8")

        # Split on ## headings
        sections: dict[str, str] = {}
        current_heading = None
        current_lines: list[str] = []
        for line in text.splitlines():
            m = re.match(r"^##\s+(.+)", line)
            if m:
                if current_heading is not None:
                    sections[current_heading.strip().lower()] = "\n".join(current_lines).strip()
                current_heading = m.group(1)
                current_lines = []
            else:
                current_lines.append(line)
        if current_heading is not None:
            sections[current_heading.strip().lower()] = "\n".join(current_lines).strip()

        dimensions = sections.get("dimensions", "").strip()

        # Extract blockquote lines from the samples section
        raw_samples = sections.get("writing samples", "")
        sample_lines = [
            re.sub(r"^>\s?", "", line).strip()
            for line in raw_samples.splitlines()
            if line.strip().startswith(">")
        ]
        # Group consecutive blockquote lines into single samples
        samples_text = "\n\n".join(
            line for line in sample_lines if line
        )

        if not dimensions and not samples_text:
            return None

        return {"dimensions": dimensions, "samples": samples_text}

    def render(self, template: str, **kwargs: str) -> str:
        """Render a template by substituting {variable} placeholders."""
        return template.format(**kwargs)
