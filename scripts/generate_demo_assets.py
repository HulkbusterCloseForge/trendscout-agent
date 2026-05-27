#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INBOX = ROOT / "samples" / "inbox"
AUDIO = ROOT / "samples" / "audio"

CLIPS = [
    ("ai_real_estate_tools_01", "red", "AI real estate tools automate listing videos and agent follow-up."),
    ("ai_real_estate_tools_02", "blue", "New AI tools help real estate teams turn property clips into marketing."),
    ("ai_real_estate_tools_03", "green", "Real estate automation saves agents hours every week."),
    ("restaurant_food_trend_reject", "purple", "Restaurant food trend unrelated to AI real estate tools."),
]


def run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True)


def main() -> None:
    if not shutil.which("ffmpeg"):
        raise SystemExit("ffmpeg required")
    INBOX.mkdir(parents=True, exist_ok=True)
    AUDIO.mkdir(parents=True, exist_ok=True)
    for idx, (name, color, caption) in enumerate(CLIPS):
        out = INBOX / f"{name}.mp4"
        run([
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", f"color=c={color}:s=720x1280:d=4",
            "-f", "lavfi", "-i", f"sine=frequency={440 + idx * 80}:duration=4",
            "-c:v", "libx264", "-c:a", "aac", "-shortest", str(out),
        ])
        (INBOX / f"{name}.mp4.json").write_text(json.dumps({"caption": caption, "title": name.replace("_", " ")}, indent=2))
    run([
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", "sine=frequency=110:duration=45",
        "-f", "lavfi", "-i", "sine=frequency=880:duration=0.035",
        "-filter_complex", "[0:a]volume=0.12[bed];[1:a]volume=0.9,aloop=loop=-1:size=1600,atrim=0:45[click];[bed][click]amix=inputs=2:duration=first,alimiter=limit=0.9[a]",
        "-map", "[a]", str(AUDIO / "demo_120bpm.wav"),
    ])
    print(f"Demo assets written to {INBOX} and {AUDIO}")


if __name__ == "__main__":
    main()
