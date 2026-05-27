from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass
class TranscriptSegment:
    start: float
    end: float
    text: str


@dataclass
class VideoTranscript:
    source_path: str
    source_url: str = ""
    title: str = ""
    transcript_text: str = ""
    segments: list[TranscriptSegment] = field(default_factory=list)
    method: str = "sidecar"

    def to_dict(self) -> dict:
        data = asdict(self)
        data["segments"] = [asdict(s) for s in self.segments]
        return data


def require_ffmpeg() -> None:
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        raise RuntimeError("ffmpeg and ffprobe are required")


def extract_audio(video_path: Path, audio_path: Path) -> Path:
    """Extract mono 16 kHz WAV for downstream transcription."""
    require_ffmpeg()
    audio_path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([
        "ffmpeg", "-y", "-i", str(video_path), "-vn", "-ac", "1", "-ar", "16000", str(audio_path)
    ], check=True, capture_output=True)
    return audio_path


def load_sidecar_transcript(video_path: Path) -> str:
    """Load demo/provider transcript sidecars before paid transcription.

    Supported files:
    - `clip.mp4.transcript.txt`
    - `clip.transcript.txt`
    - existing sample metadata JSON with caption/description/transcript fields
    """
    candidates = [
        video_path.with_suffix(video_path.suffix + ".transcript.txt"),
        video_path.with_suffix(".transcript.txt"),
        video_path.with_suffix(video_path.suffix + ".json"),
        video_path.with_suffix(".json"),
    ]
    for path in candidates:
        if not path.exists():
            continue
        if path.suffix == ".txt":
            text = path.read_text().strip()
            if text:
                return text
        if path.suffix == ".json":
            try:
                data = json.loads(path.read_text())
            except Exception:
                continue
            parts = [str(data.get(k, "")).strip() for k in ["transcript", "caption", "description", "title"]]
            text = "\n".join(p for p in parts if p)
            if text:
                return text
    return ""


def transcript_from_sidecar(video_path: Path, *, source_url: str = "", title: str = "") -> VideoTranscript:
    text = load_sidecar_transcript(video_path)
    return VideoTranscript(
        source_path=str(video_path),
        source_url=source_url,
        title=title or video_path.stem,
        transcript_text=text,
        segments=[TranscriptSegment(0.0, 0.0, text)] if text else [],
        method="sidecar",
    )
