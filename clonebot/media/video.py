"""Video frame and audio extraction."""

import subprocess
import tempfile
from pathlib import Path

import cv2

from clonebot.config.settings import get_settings


def extract_frames(video_path: Path, max_frames: int | None = None) -> list[Path]:
    """Extract evenly-spaced frames from a video as temp JPEG files."""
    settings = get_settings()
    if max_frames is None:
        max_frames = settings.video_max_frames

    cap = cv2.VideoCapture(str(video_path))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    if total_frames <= 0:
        cap.release()
        return []

    # Calculate evenly-spaced frame indices
    if total_frames <= max_frames:
        indices = list(range(total_frames))
    else:
        step = total_frames / max_frames
        indices = [int(step * i) for i in range(max_frames)]

    temp_dir = Path(tempfile.mkdtemp(prefix="clonebot_frames_"))
    extracted: list[Path] = []

    for idx in indices:
        cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ret, frame = cap.read()
        if not ret:
            continue
        out_path = temp_dir / f"frame_{idx:06d}.jpg"
        cv2.imwrite(str(out_path), frame)
        extracted.append(out_path)

    cap.release()
    return extracted


def extract_audio(video_path: Path) -> Path | None:
    """Extract audio from video as WAV using ffmpeg. Returns None if ffmpeg unavailable."""
    temp_dir = Path(tempfile.mkdtemp(prefix="clonebot_audio_"))
    out_path = temp_dir / "audio.wav"

    try:
        subprocess.run(
            [
                "ffmpeg", "-i", str(video_path),
                "-vn", "-acodec", "pcm_s16le",
                "-ar", "16000", "-ac", "1",
                str(out_path),
                "-y", "-loglevel", "error",
            ],
            check=True,
            capture_output=True,
        )
        if out_path.exists() and out_path.stat().st_size > 0:
            return out_path
        return None
    except (FileNotFoundError, subprocess.CalledProcessError):
        return None
