"""Audio transcription via OpenAI Whisper API."""

from pathlib import Path

from clonebot.config.settings import get_settings


def transcribe_audio(audio_path: Path) -> str:
    """Transcribe an audio file using the OpenAI Whisper API."""
    from openai import OpenAI

    settings = get_settings()
    client = OpenAI(api_key=settings.openai_api_key)

    with open(audio_path, "rb") as f:
        transcript = client.audio.transcriptions.create(
            model=settings.whisper_model,
            file=f,
        )
    return transcript.text
