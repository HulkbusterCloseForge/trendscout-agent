from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from .captioned_clips import build_captioned_clip_pack_from_transcripts
from .config import AutomationConfig, SourceType, Strictness
from .llm import build_search_plan, verify_candidate
from .moment_selection import _keyword_hits, _keywords
from .sources import CandidateClip, discover_candidates
from .transcript import TranscriptSegment, VideoTranscript

ROOT = Path(__file__).resolve().parents[2]


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def local_secret_fallbacks() -> None:
    apify = ROOT / "secrets" / "apify-api-token.txt"
    if apify.exists() and not os.environ.get("APIFY_API_TOKEN"):
        os.environ["APIFY_API_TOKEN"] = apify.read_text().strip()


def transcribe_with_openai(video_path: Path, out_json: Path, *, language: str = "en") -> dict | None:
    if not os.environ.get("OPENAI_API_KEY") or not shutil.which("curl"):
        return None
    out_json.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as td:
        audio = Path(td) / "audio.m4a"
        subprocess.run([
            "ffmpeg", "-y", "-i", str(video_path), "-vn", "-ac", "1", "-ar", "16000", "-t", "120", str(audio)
        ], check=True, capture_output=True)
        api_base = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
        subprocess.run([
            "curl", "-sS", f"{api_base}/audio/transcriptions",
            "-H", f"Authorization: Bearer {os.environ['OPENAI_API_KEY']}",
            "-H", "Accept: application/json",
            "-F", f"file=@{audio}",
            "-F", "model=whisper-1",
            "-F", "response_format=verbose_json",
            "-F", "timestamp_granularities[]=segment",
            "-F", f"language={language}",
            "-o", str(out_json),
        ], check=True)
    return json.loads(out_json.read_text())


def _metadata_fallback_transcript(candidate: CandidateClip) -> VideoTranscript:
    text = str(candidate.metadata.get("caption") or candidate.metadata.get("description") or candidate.metadata.get("title") or "").strip()
    duration = float(candidate.metadata.get("duration") or 6)
    return VideoTranscript(
        source_path=str(candidate.path),
        source_url=candidate.source_url,
        title=str(candidate.metadata.get("title") or candidate.path.stem),
        transcript_text=text,
        segments=[TranscriptSegment(0.0, min(8.0, max(1.0, duration)), text[:240])] if text else [],
        method="metadata_caption_fallback",
    )


def transcript_from_candidate(candidate: CandidateClip, idx: int, transcript_dir: Path, *, niche: str, transcribe: bool = True) -> VideoTranscript:
    data = None
    if transcribe:
        try:
            data = transcribe_with_openai(candidate.path, transcript_dir / f"source_{idx:02d}.verbose.json")
        except Exception as exc:
            (transcript_dir / f"source_{idx:02d}.transcribe_error.txt").write_text(str(exc))
            data = None
    if data:
        segments = [
            TranscriptSegment(float(s.get("start", 0)), float(s.get("end", 0)), " ".join(str(s.get("text", "")).split()))
            for s in data.get("segments", [])
            if str(s.get("text", "")).strip()
        ]
        transcript_text = data.get("text", "")
        meta_text = str(candidate.metadata.get("caption") or candidate.metadata.get("description") or "")
        # TikTok/shorts often have music-only audio while the metadata/visual
        # contains the actual niche signal. If Whisper hears off-topic lyrics,
        # fall back to metadata instead of selecting nonsense moments.
        if not _keyword_hits(transcript_text, _keywords(niche)) and _keyword_hits(meta_text, _keywords(niche)):
            return _metadata_fallback_transcript(candidate)
        return VideoTranscript(
            source_path=str(candidate.path),
            source_url=candidate.source_url,
            title=str(candidate.metadata.get("title") or candidate.path.stem),
            transcript_text=transcript_text,
            segments=segments,
            method="openai_whisper_verbose_json",
        )

    return _metadata_fallback_transcript(candidate)


def run_niche(args: argparse.Namespace) -> Path:
    load_dotenv(ROOT / ".env")
    local_secret_fallbacks()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = Path(args.output_dir or ROOT / "deliveries" / f"trendscout_run_{stamp}")
    run_dir.mkdir(parents=True, exist_ok=True)

    if args.source == "apify":
        source = SourceType.APIFY_TIKTOK
    elif args.source == "youtube":
        source = SourceType.YOUTUBE
    else:
        source = SourceType.LOCAL_FOLDER
    cfg = AutomationConfig(
        run_name=f"TrendScout {args.niche}",
        interest_prompt=args.niche,
        exclusions=args.exclusions,
        sources=[source],
        strictness=Strictness.EXPLORE_ADJACENT,
        target_source_clips=args.source_limit,
        apify_results_limit=args.source_limit * 3,
        max_source_age_days=args.max_source_age_days,
        max_source_duration_seconds=args.max_source_duration,
        min_source_duration_seconds=2,
        local_inbox=args.local_inbox,
        output_dir=str(ROOT / "output"),
    )
    os.environ.setdefault("APIFY_RESULTS_LIMIT", str(args.source_limit * 3))
    plan = build_search_plan(cfg)
    candidates = discover_candidates(cfg, plan, run_dir)
    accepted: list[CandidateClip] = []
    rejected: list[dict] = []
    for candidate in candidates:
        decision = verify_candidate(cfg, plan, candidate.metadata, len(accepted))
        item = {"source_url": candidate.source_url, "path": str(candidate.path), "decision": decision.__dict__, "metadata": candidate.metadata}
        if decision.accepted:
            accepted.append(candidate)
            if len(accepted) >= args.source_limit:
                break
        else:
            rejected.append(item)

    (run_dir / "source_plan.json").write_text(json.dumps(plan.__dict__, indent=2))
    (run_dir / "accepted_sources.json").write_text(json.dumps([
        {"path": str(c.path), "source_url": c.source_url, "metadata": c.metadata} for c in accepted
    ], indent=2, default=str))
    (run_dir / "rejected_sources.json").write_text(json.dumps(rejected, indent=2, default=str))
    if not accepted:
        raise SystemExit(f"No accepted sources for niche: {args.niche}")

    transcript_dir = run_dir / "transcripts"
    transcripts = [transcript_from_candidate(c, i, transcript_dir, niche=args.niche, transcribe=not args.no_transcribe) for i, c in enumerate(accepted, 1)]
    (run_dir / "transcripts_combined.json").write_text(json.dumps([t.to_dict() for t in transcripts], indent=2))

    pack_dir = run_dir / "clip_pack"
    pack = build_captioned_clip_pack_from_transcripts(
        niche=args.niche,
        transcripts=transcripts,
        output_dir=pack_dir,
        orientation=args.orientation,
        max_clips=args.max_clips,
        burn_captions=args.burn_captions,
    )
    print(json.dumps({"run_dir": str(run_dir), "clip_pack": str(pack_dir), "clips": [c.output_path for c in pack.clips]}, indent=2))
    return pack_dir


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="trendscout", description="TrendScout Agent CLI")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="Run a niche-to-captioned-clips pipeline")
    run.add_argument("--niche", required=True)
    run.add_argument("--source", choices=["apify", "youtube", "local"], default="youtube")
    run.add_argument("--local-inbox", default=str(ROOT / "samples" / "inbox"))
    run.add_argument("--source-limit", type=int, default=4)
    run.add_argument("--max-clips", type=int, default=6)
    run.add_argument("--max-source-duration", type=float, default=90)
    run.add_argument("--max-source-age-days", type=int, default=1, help="Reject sources older than this many days. Default 1 for recent-news runs.")
    run.add_argument("--orientation", choices=["vertical", "horizontal", "landscape"], default="horizontal")
    run.add_argument("--exclusions", default="crypto gambling get rich quick scam")
    run.add_argument("--output-dir", default="")
    run.add_argument("--no-transcribe", action="store_true")
    run.add_argument("--burn-captions", action="store_true", help="Burn captions into MP4s. Default is off; .srt sidecars are always written.")
    run.set_defaults(func=run_niche)
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
