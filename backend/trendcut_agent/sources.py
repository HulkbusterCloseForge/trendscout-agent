from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import urllib.parse
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .config import AutomationConfig, SourceType
from .llm import SearchPlan

VIDEO_EXTS = {".mp4", ".mov", ".m4v", ".webm", ".mkv"}


@dataclass
class CandidateClip:
    path: Path
    source_url: str
    metadata: dict
    fingerprint: str


def apify_reject_reason(item: dict[str, Any], config: AutomationConfig) -> str | None:
    if item.get("isSlideshow"):
        return "slideshow source rejected"
    video_meta = item.get("videoMeta") or {}
    duration = float(video_meta.get("duration") or item.get("duration") or 0)
    if duration and duration < float(getattr(config, "min_source_duration_seconds", 1.0)):
        return f"source too short ({duration:.1f}s)"
    if duration and duration > float(getattr(config, "max_source_duration_seconds", 90.0)):
        return f"source too long ({duration:.1f}s)"
    if item.get("isAd"):
        return "ad source rejected"
    return None


def extract_apify_tiktok_mp4(item: dict[str, Any]) -> str | None:
    return item.get("videoMeta", {}).get("downloadAddr") or (item.get("mediaUrls") or [None])[0]


def file_fingerprint(path: Path, sample_bytes: int = 1024 * 1024) -> str:
    """Stable source fingerprint fallback based on file bytes."""
    h = hashlib.sha256()
    h.update(str(path.name).encode())
    with path.open("rb") as f:
        h.update(f.read(sample_bytes))
    return h.hexdigest()


def audio_fingerprint(path: Path) -> str:
    """Content fingerprint for similar-audio dedupe.

    MVP approach: decode the first 20 seconds to low-rate mono PCM and hash it.
    This catches exact/reposted audio much better than source URL alone without
    adding heavy dependencies.
    """
    with tempfile.TemporaryDirectory() as td:
        raw = Path(td) / "audio.raw"
        cmd = [
            "ffmpeg", "-y", "-i", str(path),
            "-t", "20", "-vn", "-ac", "1", "-ar", "8000", "-f", "s16le", str(raw),
        ]
        try:
            subprocess.run(cmd, check=True, capture_output=True, timeout=60)
            data = raw.read_bytes()
            if data:
                return hashlib.sha256(data).hexdigest()
        except Exception:
            pass
    return file_fingerprint(path)


def list_local_sources(folder: Path) -> list[Path]:
    folder.mkdir(parents=True, exist_ok=True)
    return [p for p in sorted(folder.glob("*")) if p.is_file() and p.suffix.lower() in VIDEO_EXTS]


def sidecar_metadata(path: Path) -> dict:
    meta = {"filename": path.name, "title": path.stem, "source_url": f"local:{path.name}"}
    for ext in [".json", ".txt", ".caption.txt"]:
        sidecar = path.with_suffix(path.suffix + ext)
        if sidecar.exists():
            try:
                if ext == ".json":
                    meta.update(json.loads(sidecar.read_text()))
                else:
                    meta["caption"] = sidecar.read_text()[:4000]
            except Exception as exc:
                meta["sidecar_error"] = str(exc)
    return meta


def discover_local(config: AutomationConfig, plan: SearchPlan) -> list[CandidateClip]:
    candidates = []
    for path in list_local_sources(Path(config.local_inbox)):
        meta = sidecar_metadata(path)
        meta["search_query"] = plan.query
        candidates.append(CandidateClip(path=path, source_url=meta["source_url"], metadata=meta, fingerprint=audio_fingerprint(path)))
    return candidates


def _auth_url(url: str) -> str:
    token = os.environ.get("APIFY_API_TOKEN")
    if token and "api.apify.com" in url and "token=" not in url:
        sep = "&" if "?" in url else "?"
        return f"{url}{sep}token={token}"
    return url


def download_url(url: str, output_dir: Path, filename_hint: str = "source") -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    suffix = Path(url.split("?")[0]).suffix.lower()
    if suffix not in VIDEO_EXTS:
        suffix = ".mp4"
    out = output_dir / f"{filename_hint}{suffix}"
    req = urllib.request.Request(_auth_url(url), headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=90) as response, out.open("wb") as f:
        shutil.copyfileobj(response, f)
    return out


def _load_apify_items(plan: SearchPlan, config: AutomationConfig | None = None) -> list[dict]:
    items_path = os.environ.get("APIFY_TIKTOK_ITEMS_JSON")
    if items_path and Path(items_path).exists():
        return json.loads(Path(items_path).read_text())

    token = os.environ.get("APIFY_API_TOKEN")
    actor_id = os.environ.get("APIFY_TIKTOK_ACTOR_ID") or (getattr(config, "apify_actor_id", "") if config else "") or "clockworks/tiktok-scraper"
    if not token or not actor_id:
        return []

    # Generic Apify actor call. Actor input varies by actor; this default works
    # for many search/scrape actors and is easy to override via env JSON.
    actor_input = {
        "searchQueries": [plan.query],
        "resultsPerPage": 20,
        "maxItems": int(os.environ.get("APIFY_RESULTS_LIMIT", str(getattr(config, "apify_results_limit", 40) if config else 40))),
        "shouldDownloadVideos": True,
        "shouldDownloadCovers": False,
        "shouldDownloadSubtitles": False,
    }
    if os.environ.get("APIFY_TIKTOK_ACTOR_INPUT_JSON"):
        actor_input.update(json.loads(os.environ["APIFY_TIKTOK_ACTOR_INPUT_JSON"]))
    req = urllib.request.Request(
        f"https://api.apify.com/v2/acts/{urllib.parse.quote(actor_id, safe='~')}/run-sync-get-dataset-items?token={urllib.parse.quote(token)}",
        method="POST",
        headers={"Content-Type": "application/json"},
        data=json.dumps(actor_input).encode(),
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="ignore")[:500]
        try:
            payload = json.loads(body)
            message = payload.get("error", {}).get("message") or body
        except Exception:
            message = body or exc.reason
        raise RuntimeError(f"Apify actor request failed ({exc.code}): {message}") from exc


def discover_apify_tiktok(config: AutomationConfig, plan: SearchPlan, work_dir: Path) -> list[CandidateClip]:
    """Apify TikTok/Reels-style source hook.

    Uses either a saved dataset JSON (`APIFY_TIKTOK_ITEMS_JSON`) or a live Apify
    actor (`APIFY_API_TOKEN` + `APIFY_TIKTOK_ACTOR_ID`). Downstream always gets
    local downloaded MP4 files plus source metadata.
    """
    items = _load_apify_items(plan, config)
    if not items:
        return []
    candidates = []
    for idx, item in enumerate(items):
        reject_reason = apify_reject_reason(item, config)
        mp4 = extract_apify_tiktok_mp4(item)
        if not mp4 or reject_reason:
            continue
        last_error = None
        path = None
        for attempt in range(2):
            try:
                path = download_url(mp4, work_dir / "downloads", f"apify_{idx:03d}")
                break
            except Exception as exc:
                last_error = exc
        if path is None:
            continue
        video_meta = item.get("videoMeta") or {}
        music_meta = item.get("musicMeta") or {}
        meta = {
            "filename": path.name,
            "source_url": item.get("webVideoUrl") or item.get("url") or mp4,
            "caption": item.get("text") or item.get("description") or "",
            "title": item.get("authorMeta", {}).get("name", "TikTok source"),
            "author": item.get("authorMeta", {}).get("name") or item.get("authorMeta", {}).get("nickName"),
            "duration": video_meta.get("duration") or item.get("duration"),
            "play_count": item.get("playCount"),
            "digg_count": item.get("diggCount"),
            "music_name": music_meta.get("musicName"),
            "music_author": music_meta.get("musicAuthor"),
            "search_query": plan.query,
        }
        candidates.append(CandidateClip(path=path, source_url=meta["source_url"], metadata=meta, fingerprint=audio_fingerprint(path)))
    return candidates


def _youtube_search_urls(plan: SearchPlan, config: AutomationConfig) -> list[dict[str, Any]]:
    """Return YouTube candidates using yt-dlp search, with URL-file override.

    YouTube is preferred for demos over TikTok when we need cleaner speech-first
    sources. It avoids TikTok's common music-only/text-overlay failure mode.
    """
    urls_file = os.environ.get("TRENDCUT_YOUTUBE_URLS_FILE") or os.environ.get("YOUTUBE_URLS_FILE")
    if urls_file and Path(urls_file).exists():
        urls = [u.strip() for u in Path(urls_file).read_text().splitlines() if u.strip() and not u.startswith("#")]
        items: list[dict[str, Any]] = []
        for url in urls:
            item: dict[str, Any] = {"webpage_url": url, "title": plan.query, "description": plan.query, "duration": None}
            if shutil.which("yt-dlp"):
                try:
                    proc = subprocess.run(["yt-dlp", url, "--dump-single-json", "--skip-download", "--no-playlist"], check=True, capture_output=True, text=True, timeout=90)
                    item.update(json.loads(proc.stdout))
                    item["webpage_url"] = item.get("webpage_url") or url
                except Exception:
                    pass
            items.append(item)
        return items

    if not shutil.which("yt-dlp"):
        return []
    query = os.environ.get("YOUTUBE_SEARCH_QUERY") or f"{plan.query} analysis explainer"
    limit = max(1, int(os.environ.get("YOUTUBE_SEARCH_LIMIT", str(config.target_source_clips * 3))))
    cmd = ["yt-dlp", f"ytsearch{limit}:{query}", "--dump-json", "--skip-download", "--no-playlist"]
    cookies = os.environ.get("YOUTUBE_COOKIES_FILE")
    if cookies:
        cmd[1:1] = ["--cookies", cookies]
    try:
        proc = subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=180)
    except Exception:
        return []
    out: list[dict[str, Any]] = []
    for line in proc.stdout.splitlines():
        try:
            item = json.loads(line)
        except Exception:
            continue
        url = item.get("webpage_url") or item.get("original_url") or item.get("url")
        if url:
            out.append(item)
    return out


def discover_youtube(config: AutomationConfig, plan: SearchPlan, work_dir: Path) -> list[CandidateClip]:
    items = _youtube_search_urls(plan, config)
    if not items:
        return []
    out_dir = work_dir / "youtube"
    out_dir.mkdir(parents=True, exist_ok=True)
    candidates = []
    for idx, item in enumerate(items[: max(1, config.target_source_clips * 3)]):
        url = item.get("webpage_url") or item.get("original_url") or item.get("url")
        if not url:
            continue
        duration = float(item.get("duration") or 0)
        if duration and duration < float(getattr(config, "min_source_duration_seconds", 1.0)):
            continue
        if duration and duration > float(getattr(config, "max_source_duration_seconds", 180.0)):
            continue
        out_tpl = str(out_dir / f"yt_{idx:03d}.%(ext)s")
        cmd = [
            "yt-dlp",
            "-f", "bv*[height<=720]+ba/b[height<=720]/mp4/best[height<=720]/best",
            "--merge-output-format", "mp4",
            "--no-playlist",
            "-o", out_tpl,
            url,
        ]
        cookies = os.environ.get("YOUTUBE_COOKIES_FILE")
        if cookies:
            cmd[1:1] = ["--cookies", cookies]
        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=240)
        except Exception:
            continue
        paths = sorted(out_dir.glob(f"yt_{idx:03d}.*"))
        paths = [p for p in paths if p.suffix.lower() in VIDEO_EXTS]
        if not paths:
            continue
        path = paths[0]
        description = item.get("description") or item.get("fulltitle") or item.get("title") or plan.query
        meta = {
            "filename": path.name,
            "source_url": url,
            "title": item.get("title") or path.stem,
            "caption": description,
            "author": item.get("channel") or item.get("uploader"),
            "duration": duration or item.get("duration"),
            "view_count": item.get("view_count"),
            "like_count": item.get("like_count"),
            "search_query": plan.query,
            "source_platform": "youtube",
        }
        candidates.append(CandidateClip(path=path, source_url=url, metadata=meta, fingerprint=audio_fingerprint(path)))
        if len(candidates) >= config.target_source_clips:
            break
    return candidates


def discover_candidates(config: AutomationConfig, plan: SearchPlan, work_dir: Path) -> list[CandidateClip]:
    all_candidates: list[CandidateClip] = []
    source_values = {s.value if hasattr(s, "value") else s for s in config.sources}
    if SourceType.LOCAL_FOLDER.value in source_values:
        all_candidates.extend(discover_local(config, plan))
    if SourceType.APIFY_TIKTOK.value in source_values:
        all_candidates.extend(discover_apify_tiktok(config, plan, work_dir))
    if SourceType.YOUTUBE.value in source_values:
        all_candidates.extend(discover_youtube(config, plan, work_dir))
    return all_candidates
