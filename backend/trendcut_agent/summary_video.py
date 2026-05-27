from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import textwrap
from dataclasses import asdict, dataclass, field
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


@dataclass
class SummaryBeat:
    title: str
    body: str
    source: str = ""


@dataclass
class SummaryVideoPlan:
    niche: str
    headline: str
    beats: list[SummaryBeat]
    orientation: str = "vertical"
    seconds_per_beat: float = 4.0
    output_path: Path = Path("summary.mp4")
    source_notes: list[dict] = field(default_factory=list)


def require_ffmpeg() -> None:
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        raise RuntimeError("ffmpeg and ffprobe are required")


def _size(orientation: str) -> tuple[int, int]:
    return (1280, 720) if orientation == "horizontal" else (1080, 1920)


def _font(size: int, bold: bool = True) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    names = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    ]
    for name in names:
        if Path(name).exists():
            return ImageFont.truetype(name, size=size)
    return ImageFont.load_default()


def _wrap(text: str, width: int) -> list[str]:
    return textwrap.wrap(text, width=width, break_long_words=False) or [""]


def _gradient(size: tuple[int, int], c1: tuple[int, int, int], c2: tuple[int, int, int]) -> Image.Image:
    w, h = size
    img = Image.new("RGB", size, c1)
    pix = img.load()
    for y in range(h):
        t = y / max(1, h - 1)
        for x in range(w):
            # diagonal blend with a light vignette
            d = (x / max(1, w - 1) * 0.35) + (t * 0.65)
            r = int(c1[0] * (1 - d) + c2[0] * d)
            g = int(c1[1] * (1 - d) + c2[1] * d)
            b = int(c1[2] * (1 - d) + c2[2] * d)
            pix[x, y] = (r, g, b)
    return img


def _draw_wrapped(draw: ImageDraw.ImageDraw, xy: tuple[int, int], lines: list[str], font, fill, line_gap: int) -> int:
    x, y = xy
    for line in lines:
        draw.text((x, y), line, font=font, fill=fill)
        bbox = draw.textbbox((x, y), line, font=font)
        y += (bbox[3] - bbox[1]) + line_gap
    return y


def _card_image(beat: SummaryBeat, idx: int, total: int, niche: str, orientation: str) -> Image.Image:
    w, h = _size(orientation)
    palettes = [
        ((6, 17, 31), (25, 77, 122)),
        ((18, 7, 31), (108, 45, 143)),
        ((6, 27, 22), (25, 116, 92)),
        ((31, 19, 4), (154, 91, 18)),
        ((17, 24, 39), (51, 65, 85)),
    ]
    bg = _gradient((w, h), *palettes[idx % len(palettes)])
    draw = ImageDraw.Draw(bg, "RGBA")

    margin = 82 if orientation == "vertical" else 70
    title_font = _font(64 if orientation == "vertical" else 44, True)
    body_font = _font(45 if orientation == "vertical" else 30, False)
    meta_font = _font(28 if orientation == "vertical" else 20, True)
    source_font = _font(27 if orientation == "vertical" else 20, False)
    title_wrap = 24 if orientation == "vertical" else 42
    body_wrap = 31 if orientation == "vertical" else 68

    # soft geometric accents
    draw.rectangle((margin, margin, w - margin, h - margin), fill=(255, 255, 255, 16), outline=(255, 255, 255, 34), width=2)
    draw.ellipse((w - margin - 360, margin + 60, w + 180, margin + 600), fill=(56, 189, 248, 42))
    draw.ellipse((-220, int(h * 0.56), 420, int(h * 0.56) + 640), fill=(168, 85, 247, 34))

    draw.text((margin, margin + 26), niche.upper(), font=meta_font, fill=(147, 197, 253, 255))
    draw.text((w - margin - 150, margin + 26), f"{idx + 1}/{total}", font=meta_font, fill=(203, 213, 225, 230))

    _draw_wrapped(draw, (margin, int(h * 0.20)), _wrap(beat.title, title_wrap), title_font, (255, 255, 255, 255), 16)
    _draw_wrapped(draw, (margin, int(h * 0.43)), _wrap(beat.body, body_wrap), body_font, (229, 231, 235, 255), 13)

    if beat.source:
        draw.rectangle((margin, int(h * 0.76), w - margin, int(h * 0.86)), fill=(15, 23, 42, 110))
        _draw_wrapped(draw, (margin + 24, int(h * 0.775)), _wrap(beat.source, body_wrap), source_font, (203, 213, 225, 255), 8)

    # progress bar
    bar_y = h - margin - 44
    draw.rectangle((margin, bar_y, w - margin, bar_y + 12), fill=(255, 255, 255, 35))
    progress = int((idx + 1) / max(1, total) * (w - 2 * margin))
    draw.rectangle((margin, bar_y, margin + progress, bar_y + 12), fill=(56, 189, 248, 230))
    return bg


def build_summary_video(plan: SummaryVideoPlan) -> Path:
    require_ffmpeg()
    if not plan.beats:
        raise ValueError("at least one summary beat is required")
    output_path = Path(plan.output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        scene_paths: list[Path] = []
        for idx, beat in enumerate(plan.beats):
            image_path = td_path / f"card_{idx:03d}.png"
            _card_image(beat, idx, len(plan.beats), plan.niche, plan.orientation).save(image_path)
            scene = td_path / f"scene_{idx:03d}.mp4"
            cmd = [
                "ffmpeg", "-y",
                "-loop", "1", "-framerate", "30", "-i", str(image_path),
                "-f", "lavfi", "-i", f"anullsrc=channel_layout=stereo:sample_rate=44100:d={plan.seconds_per_beat}",
                "-t", str(plan.seconds_per_beat),
                "-vf", "format=yuv420p",
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                "-c:a", "aac", "-b:a", "96k",
                "-shortest", str(scene),
            ]
            subprocess.run(cmd, check=True, capture_output=True)
            scene_paths.append(scene)

        concat_file = td_path / "concat.txt"
        concat_file.write_text("".join(f"file '{p.as_posix()}'\n" for p in scene_paths))
        subprocess.run([
            "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_file),
            "-c", "copy", str(output_path)
        ], check=True, capture_output=True)

    manifest = output_path.with_suffix(".summary.json")
    manifest.write_text(json.dumps({
        "niche": plan.niche,
        "headline": plan.headline,
        "orientation": plan.orientation,
        "seconds_per_beat": plan.seconds_per_beat,
        "beats": [asdict(b) for b in plan.beats],
        "source_notes": plan.source_notes,
        "output_path": str(output_path),
    }, indent=2))
    return output_path
