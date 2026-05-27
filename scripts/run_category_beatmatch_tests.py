from __future__ import annotations

import hashlib
import json
import math
import os
import pathlib
import subprocess
import tempfile
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

from trendcut_agent.beatmatch import detect_bpm, ffprobe_duration, video_filter
from trendcut_agent.config import AutomationConfig, Strictness
from trendcut_agent.google_outputs import deliver_outputs
from trendcut_agent.llm import build_search_plan, verify_candidate
from trendcut_agent.sources import apify_reject_reason, download_url, extract_apify_tiktok_mp4

ROOT = pathlib.Path(__file__).resolve().parents[1]
TOKEN_PATH = ROOT / "secrets" / "apify-api-token.txt"
MUSIC_PATH = ROOT / "samples/audio/user_song_XD6ASbQtKxw/from_33.wav"
OUT_ROOT = ROOT / "output/category_tests_20260527"


@dataclass
class CategorySpec:
    name: str
    run_name: str
    query: str
    interest: str
    exclusions: str
    target_clips: int = 4
    max_items: int = 6
    max_duration: float = 75.0
    final_duration: int = 15
    beat_density: int = 2
    transient_filter: str = ""


def apify_run_items(query: str, max_items: int) -> list[dict[str, Any]]:
    token = TOKEN_PATH.read_text().strip() or os.environ.get("APIFY_API_TOKEN")
    actor_id = "clockworks/tiktok-scraper"
    actor_input = {
        "searchQueries": [query],
        "resultsPerPage": max_items,
        "maxItems": max_items,
        "shouldDownloadVideos": True,
        "shouldDownloadCovers": False,
        "shouldDownloadSubtitles": False,
    }
    url = f"https://api.apify.com/v2/acts/{urllib.parse.quote(actor_id, safe='~')}/runs?token={urllib.parse.quote(token)}"
    req = urllib.request.Request(url, method="POST", headers={"Content-Type": "application/json"}, data=json.dumps(actor_input).encode())
    with urllib.request.urlopen(req, timeout=60) as resp:
        run = json.loads(resp.read().decode())["data"]
    run_id = run["id"]
    final = run
    for _ in range(40):
        time.sleep(5)
        with urllib.request.urlopen(f"https://api.apify.com/v2/actor-runs/{run_id}?token={urllib.parse.quote(token)}", timeout=30) as resp:
            final = json.loads(resp.read().decode())["data"]
        if final.get("status") in {"SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT"}:
            break
    if final.get("status") != "SUCCEEDED":
        raise RuntimeError(f"Apify run {run_id} ended with {final.get('status')}")
    dataset_id = final.get("defaultDatasetId")
    if not dataset_id:
        return []
    with urllib.request.urlopen(f"https://api.apify.com/v2/datasets/{dataset_id}/items?clean=true&token={urllib.parse.quote(token)}", timeout=60) as resp:
        items = json.loads(resp.read().decode())
    return items


def item_meta(item: dict[str, Any]) -> dict[str, Any]:
    mp4 = extract_apify_tiktok_mp4(item)
    return {
        "title": item.get("authorMeta", {}).get("name") or item.get("authorMeta", {}).get("nickName") or "TikTok source",
        "author": item.get("authorMeta", {}).get("name") or item.get("authorMeta", {}).get("nickName"),
        "caption": item.get("text") or item.get("description") or "",
        "source_url": item.get("webVideoUrl") or item.get("url") or mp4,
        "duration": (item.get("videoMeta") or {}).get("duration") or item.get("duration"),
        "play_count": item.get("playCount"),
        "mp4": mp4,
    }


def select_candidates(spec: CategorySpec, items: list[dict[str, Any]], work_dir: pathlib.Path) -> tuple[list[dict], list[dict]]:
    cfg = AutomationConfig(
        run_name=spec.run_name,
        interest_prompt=spec.interest,
        exclusions=spec.exclusions,
        strictness=Strictness.BALANCED,
        target_source_clips=spec.target_clips,
        min_source_duration_seconds=2.0,
        max_source_duration_seconds=spec.max_duration,
    )
    plan = build_search_plan(cfg)
    accepted: list[dict] = []
    rejected: list[dict] = []
    seen_authors: set[str] = set()
    for idx, item in enumerate(items):
        meta = item_meta(item)
        mp4 = meta.pop("mp4")
        reject = apify_reject_reason(item, cfg)
        if reject or not mp4:
            rejected.append({"idx": idx, "reason": reject or "no mp4", "metadata": meta})
            continue
        decision = verify_candidate(cfg, plan, meta, len(accepted))
        if not decision.accepted:
            rejected.append({"idx": idx, "decision": decision.__dict__, "metadata": meta})
            continue
        author = str(meta.get("author") or meta.get("title") or "").lower().strip()
        if author and author in seen_authors:
            rejected.append({"idx": idx, "reason": "duplicate author/source account for demo diversity", "decision": decision.__dict__, "metadata": meta})
            continue
        try:
            path = download_url(mp4, work_dir / "downloads", f"apify_{idx:03d}")
        except Exception as exc:
            rejected.append({"idx": idx, "reason": f"download failed: {exc}", "metadata": meta})
            continue
        seen_authors.add(author)
        accepted.append({"idx": idx, "path": str(path), "source_url": meta["source_url"], "decision": decision.__dict__, "metadata": meta})
        if len(accepted) >= spec.target_clips:
            break
    return accepted, rejected


def has_audio(path: pathlib.Path) -> bool:
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries", "stream=index", "-of", "csv=p=0", str(path)], capture_output=True, text=True)
    return bool(r.stdout.strip())


def render_continuous_song_with_transients(spec: CategorySpec, accepted: list[dict], out_path: pathlib.Path) -> pathlib.Path:
    clips = [(pathlib.Path(a["path"]), a["source_url"]) for a in accepted]
    if not clips:
        raise RuntimeError("No accepted clips to render")
    bpm = detect_bpm(MUSIC_PATH)
    segment_duration = max(0.35, (60.0 / bpm) * spec.beat_density)
    segment_count = max(1, math.ceil(spec.final_duration / segment_duration))
    vf = video_filter("vertical") + ",eq=contrast=1.04:saturation=1.06"
    ordered = sorted(clips, key=lambda c: hashlib.sha1(str(c[1]).encode()).hexdigest())
    out_path.parent.mkdir(parents=True, exist_ok=True)
    transient_filter = spec.transient_filter or (
        "aformat=sample_rates=44100:channel_layouts=stereo,"
        "highpass=f=900,lowpass=f=6500,"
        "agate=threshold=-30dB:ratio=7:attack=1:release=45,"
        "acompressor=threshold=-18dB:ratio=3.5:attack=1:release=45,"
        "volume=1.25,alimiter=limit=0.72"
    )
    with tempfile.TemporaryDirectory() as td_raw:
        td = pathlib.Path(td_raw)
        video_segs: list[pathlib.Path] = []
        hit_segs: list[pathlib.Path] = []
        for idx in range(segment_count):
            clip_path, source_url = ordered[(idx * 3) % len(ordered)] if len(ordered) > 1 else ordered[0]
            clip_duration = ffprobe_duration(clip_path)
            usable = max(0.0, clip_duration - segment_duration - 0.1)
            offset = 0.0 if usable <= 0 else ((idx + 1) * segment_duration * 1.618) % usable
            vseg = td / f"vseg_{idx:04d}.mp4"
            subprocess.run([
                "ffmpeg", "-y", "-ss", f"{offset:.3f}", "-i", str(clip_path), "-t", f"{segment_duration:.3f}",
                "-an", "-vf", vf, "-c:v", "libx264", "-preset", "veryfast", "-crf", "22", str(vseg)
            ], check=True, capture_output=True)
            video_segs.append(vseg)
            hseg = td / f"hit_{idx:04d}.wav"
            if has_audio(clip_path):
                subprocess.run([
                    "ffmpeg", "-y", "-ss", f"{offset:.3f}", "-i", str(clip_path), "-t", f"{segment_duration:.3f}",
                    "-vn", "-af", transient_filter, "-ar", "44100", "-ac", "2", str(hseg)
                ], check=True, capture_output=True)
            else:
                subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100", "-t", f"{segment_duration:.3f}", str(hseg)], check=True, capture_output=True)
            hit_segs.append(hseg)
        vconcat = td / "video_concat.txt"
        vconcat.write_text("".join(f"file '{p.as_posix()}'\n" for p in video_segs))
        silent = td / "silent_video.mp4"
        subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(vconcat), "-c", "copy", str(silent)], check=True, capture_output=True)
        hconcat = td / "hit_concat.txt"
        hconcat.write_text("".join(f"file '{p.as_posix()}'\n" for p in hit_segs))
        hits = td / "hits.wav"
        subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(hconcat), "-t", str(spec.final_duration), "-c:a", "pcm_s16le", str(hits)], check=True, capture_output=True)
        fc = (
            f"[1:a]volume=0.80,atrim=0:{spec.final_duration},aformat=sample_rates=44100:channel_layouts=stereo[song];"
            "[2:a]volume=1.35,acompressor=threshold=-16dB:ratio=2.4:attack=1:release=55,alimiter=limit=0.75,asplit=2[hits_sc][hits_mix];"
            "[song][hits_sc]sidechaincompress=threshold=0.04:ratio=2.2:attack=2:release=90[ducked_song];"
            "[ducked_song][hits_mix]amix=inputs=2:duration=first:normalize=0,"
            f"afade=t=in:st=0:d=0.04,afade=t=out:st={max(0, spec.final_duration - 0.25)}:d=0.25,alimiter=limit=0.95[a]"
        )
        subprocess.run([
            "ffmpeg", "-y", "-i", str(silent), "-i", str(MUSIC_PATH), "-i", str(hits), "-t", str(spec.final_duration),
            "-filter_complex", fc, "-map", "0:v:0", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", str(out_path)
        ], check=True, capture_output=True)
    return out_path


def run_spec(spec: CategorySpec) -> dict[str, Any]:
    work_dir = OUT_ROOT / spec.name
    work_dir.mkdir(parents=True, exist_ok=True)
    items = apify_run_items(spec.query, spec.max_items)
    (work_dir / "apify_items.json").write_text(json.dumps(items, indent=2))
    accepted, rejected = select_candidates(spec, items, work_dir)
    output_path = work_dir / f"{spec.name}_continuous_song_transients.mp4"
    delivery = {}
    status = "failed"
    error = ""
    if accepted:
        try:
            render_continuous_song_with_transients(spec, accepted, output_path)
            status = "completed"
            record = {
                "run_id": f"category_test_{spec.name}_20260527",
                "status": status,
                "error": "",
                "config": {"run_name": spec.run_name, "interest_prompt": spec.interest, "category": spec.name},
                "accepted": accepted,
                "rejected": rejected,
                "output_path": str(output_path),
                "warnings": ["Continuous user-selected song with filtered transient layer only; raw source audio stripped."],
            }
            delivery = deliver_outputs(output_path, record, ROOT / "output")
            record["delivery"] = delivery
            (work_dir / "record.json").write_text(json.dumps(record, indent=2, default=str))
        except Exception as exc:
            error = str(exc)
    else:
        error = "No accepted clips"
    return {
        "category": spec.name,
        "status": status,
        "error": error,
        "accepted": len(accepted),
        "rejected": len(rejected),
        "accepted_titles": [a.get("metadata", {}).get("title") for a in accepted],
        "drive_url": delivery.get("drive_url"),
        "sheet_url": delivery.get("sheet_url"),
        "output_path": str(output_path) if output_path.exists() else "",
    }


def main() -> None:
    specs = [
        CategorySpec(
            name="cooking",
            run_name="TrendScout Cooking Beatmatch Test",
            query="cooking food prep chopping sizzling plating recipe",
            interest="cooking food prep chopping sizzling plating flip pour chef recipe closeup",
            exclusions="mukbang, eating, restaurant review, talking head, podcast, slideshow, still image, ad, crypto, tennis, basketball",
            max_items=6,
            target_clips=4,
            max_duration=75,
            transient_filter="aformat=sample_rates=44100:channel_layouts=stereo,highpass=f=700,lowpass=f=7200,agate=threshold=-32dB:ratio=6:attack=1:release=55,acompressor=threshold=-18dB:ratio=3.0:attack=1:release=55,volume=1.25,alimiter=limit=0.72",
        ),
        CategorySpec(
            name="basketball",
            run_name="TrendScout Basketball Beatmatch Test",
            query="basketball dunk crossover ankle breaker highlights",
            interest="basketball dunk crossover ankle breaker block handles highlight slam fastbreak",
            exclusions="nba 2k, video game, tutorial, podcast, slideshow, still image, ad, crypto, tennis, cooking",
            max_items=6,
            target_clips=4,
            max_duration=75,
            transient_filter="aformat=sample_rates=44100:channel_layouts=stereo,highpass=f=500,lowpass=f=6500,agate=threshold=-30dB:ratio=6:attack=1:release=60,acompressor=threshold=-18dB:ratio=3.2:attack=1:release=60,volume=1.35,alimiter=limit=0.74",
        ),
    ]
    results = [run_spec(spec) for spec in specs]
    out = OUT_ROOT / "summary.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(results, indent=2))
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
