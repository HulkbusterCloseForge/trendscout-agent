#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from trendcut_agent.captioned_clips import build_captioned_clip_pack_from_transcripts
from trendcut_agent.moment_selection import _keyword_hits, _keywords
from trendcut_agent.transcript import TranscriptSegment, VideoTranscript

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "deliveries" / "trendscout_stock_market_live_attempt_20260528"


def load_transcript(idx: int, source_path: str, source_url: str, title: str, metadata: dict) -> VideoTranscript:
    data = json.loads((RUN / "transcripts" / f"source_{idx}.verbose.json").read_text())
    segments = []
    for seg in data.get("segments", []):
        text = " ".join(str(seg.get("text", "")).split())
        if not text:
            continue
        segments.append(TranscriptSegment(float(seg.get("start", 0)), float(seg.get("end", 0)), text))
    meta_text = str(metadata.get("caption") or metadata.get("description") or "")
    transcript_text = data.get("text", "")
    if not _keyword_hits(transcript_text, _keywords("Stock Market")) and _keyword_hits(meta_text, _keywords("Stock Market")):
        duration = float(metadata.get("duration") or 6)
        return VideoTranscript(
            source_path=source_path,
            source_url=source_url,
            title=title,
            transcript_text=meta_text,
            segments=[TranscriptSegment(0.0, min(8.0, max(1.0, duration)), meta_text[:240])],
            method="metadata_caption_fallback_for_music_or_irrelevant_audio",
        )
    return VideoTranscript(
        source_path=source_path,
        source_url=source_url,
        title=title,
        transcript_text=transcript_text,
        segments=segments,
        method="openai_whisper_verbose_json",
    )


def main() -> None:
    accepted = json.loads((RUN / "accepted_manifest.json").read_text())
    transcripts = []
    for idx, item in enumerate(accepted, 1):
        transcripts.append(load_transcript(idx, item["path"], item["source_url"], item.get("metadata", {}).get("title", f"source {idx}"), item.get("metadata", {})))
    out_dir = RUN / f"transcribed_clip_pack_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    pack = build_captioned_clip_pack_from_transcripts(
        niche="Stock Market",
        transcripts=transcripts,
        output_dir=out_dir,
        orientation="vertical",
        max_clips=6,
    )
    (out_dir / "transcripts_combined.json").write_text(json.dumps([t.to_dict() for t in transcripts], indent=2))
    print(out_dir)
    print(json.dumps(pack.to_dict(), indent=2))


if __name__ == "__main__":
    main()
