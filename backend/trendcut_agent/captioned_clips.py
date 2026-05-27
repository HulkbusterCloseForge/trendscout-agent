from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .moment_selection import select_transcript_moments
from .summary_video import SummaryBeat, SummaryVideoPlan, build_summary_video
from .transcript import TranscriptSegment, VideoTranscript
from .transcript_intelligence import TranscriptEditPlan


@dataclass
class CaptionedClip:
    clip_id: str
    title: str
    caption: str
    source_quote: str = ""
    source_url: str = ""
    source_path: str = ""
    start: float | None = None
    end: float | None = None
    output_path: str = ""
    rationale: str = ""


@dataclass
class CaptionedClipPack:
    niche: str
    headline: str
    clips: list[CaptionedClip] = field(default_factory=list)
    output_dir: str = ""
    provider: str = ""
    model: str = ""

    def to_dict(self) -> dict:
        data = asdict(self)
        data["clips"] = [asdict(c) for c in self.clips]
        return data


def _safe_slug(text: str, fallback: str) -> str:
    chars = []
    for ch in text.lower():
        if ch.isalnum():
            chars.append(ch)
        elif ch in {" ", "-", "_"}:
            chars.append("-")
    slug = "".join(chars).strip("-")
    while "--" in slug:
        slug = slug.replace("--", "-")
    return (slug or fallback)[:64]


def _srt_time(seconds: float) -> str:
    seconds = max(0.0, seconds)
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    ms = int(round((seconds - int(seconds)) * 1000))
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{ms:03d}"


def _write_srt(path: Path, caption: str, duration: float) -> Path:
    path.write_text(f"1\n00:00:00,000 --> {_srt_time(duration)}\n{caption}\n")
    return path


def _subtitle_filter_arg(srt_path: Path) -> str:
    # ffmpeg subtitles filter accepts escaped absolute paths. Escape backslash,
    # colon, comma, and apostrophe for filter syntax.
    text = srt_path.as_posix().replace("\\", "\\\\").replace(":", "\\:").replace(",", "\\,").replace("'", "\\'")
    return f"subtitles='{text}':force_style='FontName=DejaVu Sans,FontSize=16,Outline=2,Shadow=1,MarginV=72,PrimaryColour=&H00FFFFFF&,OutlineColour=&H00000000&'"


def _vf_for_orientation(orientation: str, srt_path: Path | None = None) -> str:
    landscape = orientation in {"horizontal", "landscape", "16:9"}
    base = "scale=1280:720:force_original_aspect_ratio=increase,crop=1280:720,setsar=1,fps=30,format=yuv420p" if landscape else "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1,fps=30,format=yuv420p"
    if srt_path:
        return base + "," + _subtitle_filter_arg(srt_path)
    return base


def _segment_candidates(transcript: VideoTranscript) -> list[TranscriptSegment]:
    if transcript.segments:
        return [s for s in transcript.segments if s.text.strip()]
    text = transcript.transcript_text.strip()
    if not text:
        return []
    # Fallback split for non-timestamped transcripts. These are reviewable demo
    # clips, but live mode should prefer real timestamps.
    chunks = []
    sentences = [p.strip() for p in text.replace("?", ".").replace("!", ".").split(".") if p.strip()]
    t = 0.0
    for sentence in sentences:
        duration = min(8.0, max(3.0, len(sentence.split()) / 2.8))
        chunks.append(TranscriptSegment(start=t, end=t + duration, text=sentence + "."))
        t += duration
    return chunks


def build_captioned_clip_pack_from_plan(
    *,
    niche: str,
    edit_plan: TranscriptEditPlan,
    output_dir: Path,
    orientation: str = "horizontal",
    seconds_per_clip: float = 4.0,
) -> CaptionedClipPack:
    """Export one short captioned card MP4 per selected insight.

    Use this when live source clips/timestamps are unavailable. The preferred
    product path is `build_captioned_clip_pack_from_transcripts`, which cuts
    actual source video segments.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    clips: list[CaptionedClip] = []
    for idx, insight in enumerate(edit_plan.insights, 1):
        clip_id = f"clip_{idx:02d}_{_safe_slug(insight.title, f'insight-{idx}') }"
        out = output_dir / f"{clip_id}.mp4"
        build_summary_video(SummaryVideoPlan(
            niche=niche,
            headline=edit_plan.headline,
            beats=[SummaryBeat(insight.title, insight.summary, insight.quote or insight.suggested_visual)],
            orientation=orientation,
            seconds_per_beat=seconds_per_clip,
            output_path=out,
            source_notes=[{"quote": insight.quote, "suggested_visual": insight.suggested_visual}],
        ))
        clips.append(CaptionedClip(
            clip_id=clip_id,
            title=insight.title,
            caption=insight.summary,
            source_quote=insight.quote,
            output_path=str(out),
            rationale=f"Selected from transcript with importance {insight.importance:.2f}",
        ))
    return _write_pack(output_dir, niche, edit_plan.headline, clips, edit_plan.provider, edit_plan.model)


def cut_source_clip_with_caption(
    *,
    source_path: Path,
    caption: str,
    output_path: Path,
    start: float = 0.0,
    duration: float = 8.0,
    orientation: str = "horizontal",
    burn_caption: bool = False,
) -> Path:
    """Cut a source video segment and save optional caption.

    Creates both:
    - `output_path` MP4
    - `output_path.with_suffix('.srt')` caption sidecar

    Burned-in captions are OFF by default because they can clutter source clips.
    If `burn_caption=True` and subtitle burn fails, it retries without burn and
    keeps the sidecar.
    """
    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg is required")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    duration = max(0.5, duration)
    srt = _write_srt(output_path.with_suffix(".srt"), caption, duration)
    vf = _vf_for_orientation(orientation, srt if burn_caption else None)
    cmd = [
        "ffmpeg", "-y", "-ss", f"{max(0.0, start):.3f}", "-i", str(source_path), "-t", f"{duration:.3f}",
        "-vf", vf,
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
        "-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-ac", "2",
        "-shortest", str(output_path),
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True)
    except subprocess.CalledProcessError:
        fallback = [
            "ffmpeg", "-y", "-ss", f"{max(0.0, start):.3f}", "-i", str(source_path), "-t", f"{duration:.3f}",
            "-vf", _vf_for_orientation(orientation, None),
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
            "-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-ac", "2",
            "-shortest", str(output_path),
        ]
        subprocess.run(fallback, check=True, capture_output=True)
    return output_path


def build_captioned_clip_pack_from_transcripts(
    *,
    niche: str,
    transcripts: list[VideoTranscript],
    output_dir: Path,
    orientation: str = "horizontal",
    max_clips: int = 5,
    burn_captions: bool = False,
) -> CaptionedClipPack:
    """Preferred MVP output: cut source video moments into separate clips.

    Captions are always saved as `.srt` sidecars, but visual burn-in is optional
    and defaults OFF.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    # Normalize non-timestamped transcripts into pseudo segments, then select
    # the highest-signal moments. Nemotron is used inside
    # select_transcript_moments when configured.
    normalized: list[VideoTranscript] = []
    for t in transcripts:
        if t.segments:
            normalized.append(t)
        else:
            normalized.append(VideoTranscript(
                source_path=t.source_path,
                source_url=t.source_url,
                title=t.title,
                transcript_text=t.transcript_text,
                segments=_segment_candidates(t),
                method=t.method,
            ))
    moments = select_transcript_moments(niche, normalized, max_clips, max_per_transcript=min(5, max(1, max_clips)))

    clips: list[CaptionedClip] = []
    for idx, moment in enumerate(moments, 1):
        transcript = normalized[moment.transcript_index]
        title = f"Moment {idx}"
        clip_id = f"clip_{idx:02d}_{_safe_slug(moment.caption[:42], f'moment-{idx}') }"
        out = output_dir / f"{clip_id}.mp4"
        duration = max(1.0, moment.end - moment.start)
        source_path = Path(transcript.source_path)
        if source_path.exists():
            cut_source_clip_with_caption(
                source_path=source_path,
                caption=moment.caption,
                output_path=out,
                start=moment.start,
                duration=duration,
                orientation=orientation,
                burn_caption=burn_captions,
            )
        else:
            build_summary_video(SummaryVideoPlan(
                niche=niche,
                headline=f"Important moments in {niche}",
                beats=[SummaryBeat(title, moment.caption, transcript.source_url or transcript.title)],
                orientation=orientation,
                seconds_per_beat=min(8.0, duration),
                output_path=out,
            ))
        clips.append(CaptionedClip(
            clip_id=clip_id,
            title=title,
            caption=moment.caption,
            source_quote=moment.caption,
            source_url=transcript.source_url,
            source_path=transcript.source_path,
            start=moment.start,
            end=moment.end,
            output_path=str(out),
            rationale=moment.rationale,
        ))

    return _write_pack(output_dir, niche, f"Captioned moments for {niche}", clips, "transcript_segments", "timestamped-transcript")


def _write_pack(output_dir: Path, niche: str, headline: str, clips: list[CaptionedClip], provider: str, model: str) -> CaptionedClipPack:
    pack = CaptionedClipPack(niche=niche, headline=headline, clips=clips, output_dir=str(output_dir), provider=provider, model=model)
    (output_dir / "clip_pack_manifest.json").write_text(json.dumps(pack.to_dict(), indent=2))
    (output_dir / "README.md").write_text(
        "# TrendScout Captioned Clip Pack\n\n"
        "This folder is the intended product output: separate short clips plus caption sidecars and a manifest for review.\n\n"
        "## Clips\n\n" + "\n".join(f"- `{Path(c.output_path).name}` — {c.title}" for c in clips) + "\n"
    )
    return pack
