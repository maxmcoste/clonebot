"""Vision LLM analysis for images."""

import base64
from abc import ABC, abstractmethod
from pathlib import Path

from PIL import Image

from clonebot.config.settings import get_settings


def _get_media_type(path: Path) -> str:
    """Map file extension to MIME type."""
    mapping = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
        ".webp": "image/webp",
    }
    return mapping.get(path.suffix.lower(), "image/jpeg")


def _encode_image_base64(path: Path, max_size: int = 2048) -> str:
    """Open image with Pillow, resize to fit max_size, return base64 string."""
    img = Image.open(path)
    img.thumbnail((max_size, max_size))

    from io import BytesIO

    buf = BytesIO()
    fmt = "PNG" if path.suffix.lower() == ".png" else "JPEG"
    img.save(buf, format=fmt)
    return base64.b64encode(buf.getvalue()).decode("utf-8")


class VisionAnalyzer(ABC):
    @abstractmethod
    def describe_image(self, image_path: Path, context: str = "") -> str:
        """Analyze an image and return a text description."""


class OpenAIVisionAnalyzer(VisionAnalyzer):
    def describe_image(self, image_path: Path, context: str = "") -> str:
        from openai import OpenAI

        settings = get_settings()
        client = OpenAI(api_key=settings.openai_api_key)

        b64 = _encode_image_base64(image_path)
        media_type = _get_media_type(image_path)

        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "Describe this image in detail for a personal memory system. "
                            "Include people, setting, activities, emotions, and any notable objects. "
                            f"{f'Context: {context}' if context else ''}"
                        ),
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{media_type};base64,{b64}",
                        },
                    },
                ],
            }
        ]

        response = client.chat.completions.create(
            model=settings.vision_model,
            messages=messages,
            max_tokens=500,
        )
        return response.choices[0].message.content


class AnthropicVisionAnalyzer(VisionAnalyzer):
    def describe_image(self, image_path: Path, context: str = "") -> str:
        import anthropic

        settings = get_settings()
        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

        b64 = _encode_image_base64(image_path)
        media_type = _get_media_type(image_path)

        response = client.messages.create(
            model=settings.vision_model,
            max_tokens=500,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": b64,
                            },
                        },
                        {
                            "type": "text",
                            "text": (
                                "Describe this image in detail for a personal memory system. "
                                "Include people, setting, activities, emotions, and any notable objects. "
                                f"{f'Context: {context}' if context else ''}"
                            ),
                        },
                    ],
                }
            ],
        )
        return response.content[0].text


def get_vision_analyzer() -> VisionAnalyzer:
    """Factory: return the configured vision analyzer."""
    settings = get_settings()
    provider = settings.vision_provider.lower()

    if provider == "openai":
        return OpenAIVisionAnalyzer()
    elif provider in ("anthropic", "claude"):
        return AnthropicVisionAnalyzer()
    else:
        raise ValueError(f"Unsupported vision provider: {provider}")
