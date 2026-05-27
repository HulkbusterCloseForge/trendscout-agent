from __future__ import annotations

import math
import hashlib
import shutil
import subprocess
import tempfile
import wave
from dataclasses import dataclass
from pathlib import Path


@dataclass
class SourceClip:
    path: Path
    source_url: str
    rationale: str = ""


@dataclass
class BeatMatchPlan:
    audio_path: Path
    beat_density: int
    orientation: str
    final_duration_seconds: int
    clips: list[SourceClip]


def require_ffmpeg() -> None:
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        raise RuntimeError("ffmpeg and ffprobe are required")


def ffprobe_duration(path: Path) -> float:
    cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nokey=1:noprint_wrappers=1", str(path)]
    out = subprocess.check_output(cmd, text=True).strip()
    return max(0.0, float(out or 0))


def has_audio_stream(path: Path) -> bool:
    cmd = ["ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries", "stream=index", "-of", "csv=p=0", str(path)]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return bool(result.stdout.strip())


def synth_demo_audio(path: Path, duration: int = 60, bpm: int = 120) -> Path:
    """Create a hackathon-safe click/percussion demo track if no audio exists."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        return path
    # Sine + click approximation. Safe/generated, not scraped copyrighted audio.
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", f"sine=frequency=110:duration={duration}",
        "-f", "lavfi", "-i", f"sine=frequency=880:duration=0.035",
        "-filter_complex", f"[0:a]volume=0.15[bed];[1:a]volume=0.8,aloop=loop=-1:size=1600,atrim=0:{duration}[click];[bed][click]amix=inputs=2:duration=first,alimiter=limit=0.9[a]",
        "-map", "[a]", str(path)
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    return path


def _audio_to_wav(audio_path: Path, wav_path: Path) -> None:
    cmd = ["ffmpeg", "-y", "-i", str(audio_path), "-ac", "1", "-ar", "11025", "-t", "90", str(wav_path)]
    subprocess.run(cmd, check=True, capture_output=True)


def detect_bpm(audio_path: Path) -> float:
    """Tiny stdlib onset/BPM estimate. Falls back to 120 BPM when uncertain."""
    require_ffmpeg()
    with tempfile.TemporaryDirectory() as td:
        wav_path = Path(td) / "audio.wav"
        try:
            _audio_to_wav(audio_path, wav_path)
            with wave.open(str(wav_path), "rb") as w:
                rate = w.getframerate()
                frames = w.readframes(w.getnframes())
                sample_width = w.getsampwidth()
            if sample_width != 2 or not frames:
                return 120.0
            samples = [int.from_bytes(frames[i:i+2], "little", signed=True) for i in range(0, len(frames), 2)]
            win = max(1, int(rate * 0.05))
            energies = []
            for i in range(0, len(samples), win):
                chunk = samples[i:i+win]
                if not chunk:
                    continue
                energies.append(sum(abs(x) for x in chunk) / len(chunk))
            if len(energies) < 20:
                return 120.0
            avg = sum(energies) / len(energies)
            peaks = []
            for i in range(1, len(energies) - 1):
                if energies[i] > energies[i-1] and energies[i] >= energies[i+1] and energies[i] > avg * 1.35:
                    t = i * 0.05
                    if not peaks or t - peaks[-1] > 0.25:
                        peaks.append(t)
            if len(peaks) < 4:
                return 120.0
            intervals = [b - a for a, b in zip(peaks, peaks[1:]) if 0.25 <= b - a <= 2.0]
            if not intervals:
                return 120.0
            intervals.sort()
            median = intervals[len(intervals) // 2]
            bpm = 60.0 / median
            while bpm < 80:
                bpm *= 2
            while bpm > 180:
                bpm /= 2
            return round(bpm, 2)
        except Exception:
            return 120.0


def video_filter(orientation: str) -> str:
    if orientation == "horizontal":
        return "scale=1280:720:force_original_aspect_ratio=increase,crop=1280:720,setsar=1,fps=30,format=yuv420p"
    return "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1,fps=30,format=yuv420p"


def build_beatmatched_video(plan: BeatMatchPlan, output_path: Path) -> Path:
    require_ffmpeg()
    if plan.beat_density not in (1, 2, 4, 8):
        raise ValueError("beat_density must be one of 1, 2, 4, 8")
    if not plan.clips:
        raise ValueError("at least one source clip is required")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    bpm = detect_bpm(plan.audio_path)
    segment_duration = max(0.35, (60.0 / bpm) * plan.beat_density)
    segment_count = max(1, math.ceil(plan.final_duration_seconds / segment_duration))
    vf = video_filter(plan.orientation)

    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        segment_paths = []
        # Deterministic but varied ordering: spread repeated clips instead of
        # exhausting one source at a time.
        ordered_clips = sorted(plan.clips, key=lambda c: hashlib.sha1(str(c.source_url).encode()).hexdigest())
        for idx in range(segment_count):
            clip = ordered_clips[(idx * 3) % len(ordered_clips)] if len(ordered_clips) > 1 else ordered_clips[0]
            clip_duration = ffprobe_duration(clip.path)
            # Deterministic offset cycling, with a short safety margin.
            usable = max(0.0, clip_duration - segment_duration - 0.1)
            offset = 0.0 if usable <= 0 else ((idx + 1) * segment_duration * 1.618) % usable
            seg = td_path / f"seg_{idx:04d}.mp4"
            if has_audio_stream(clip.path):
                cmd = [
                    "ffmpeg", "-y",
                    "-ss", f"{offset:.3f}",
                    "-stream_loop", "-1",
                    "-i", str(clip.path),
                    "-t", f"{segment_duration:.3f}",
                    "-map", "0:v:0", "-map", "0:a:0",
                    "-vf", vf + ",eq=contrast=1.04:saturation=1.06",
                    "-af", "aresample=44100,volume=2.35,acompressor=threshold=-12dB:ratio=2.2:attack=2:release=60,alimiter=limit=0.95",
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
                    "-c:a", "aac", "-b:a", "160k", "-ar", "44100", "-ac", "2",
                    "-shortest", str(seg),
                ]
            else:
                cmd = [
                    "ffmpeg", "-y",
                    "-ss", f"{offset:.3f}",
                    "-stream_loop", "-1",
                    "-i", str(clip.path),
                    "-f", "lavfi", "-t", f"{segment_duration:.3f}", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
                    "-t", f"{segment_duration:.3f}",
                    "-map", "0:v:0", "-map", "1:a:0",
                    "-vf", vf + ",eq=contrast=1.04:saturation=1.06",
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
                    "-c:a", "aac", "-b:a", "160k", "-ar", "44100", "-ac", "2",
                    "-shortest", str(seg),
                ]
            subprocess.run(cmd, check=True, capture_output=True)
            segment_paths.append(seg)

        concat_file = td_path / "concat.txt"
        concat_file.write_text("".join(f"file '{p.as_posix()}'\n" for p in segment_paths))
        assembled_video = td_path / "video_with_source_audio.mp4"
        subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_file), "-c", "copy", str(assembled_video)], check=True, capture_output=True)

        cmd = [
            "ffmpeg", "-y",
            "-i", str(assembled_video),
            "-stream_loop", "-1", "-i", str(plan.audio_path),
            "-t", str(plan.final_duration_seconds),
            "-filter_complex",
            "[0:a]volume=1.0,acompressor=threshold=-12dB:ratio=2.2:attack=2:release=60,asplit=2[src_sc][src_mix];"
            "[1:a]volume=0.36,atrim=0:" + str(plan.final_duration_seconds) + "[music];"
            "[music][src_sc]sidechaincompress=threshold=0.05:ratio=3:attack=5:release=120[ducked];"
            "[ducked][src_mix]amix=inputs=2:duration=first:normalize=0,"
            "afade=t=in:st=0:d=0.08,afade=t=out:st=" + str(max(0, plan.final_duration_seconds - 0.25)) + ":d=0.25,alimiter=limit=0.95[a]",
            "-map", "0:v:0", "-map", "[a]",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
            "-shortest", str(output_path),
        ]
        subprocess.run(cmd, check=True, capture_output=True)

    return output_path
