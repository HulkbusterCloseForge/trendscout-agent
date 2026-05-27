#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from trendcut_agent.captioned_clips import build_captioned_clip_pack_from_transcripts
from trendcut_agent.transcript import TranscriptSegment, VideoTranscript

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    source = ROOT / "samples" / "inbox" / "ai_real_estate_tools_01.mp4"
    transcript = VideoTranscript(
        source_path=str(source),
        source_url="demo://ai-real-estate-tools-top-video",
        title="Demo trending video: AI real estate tools",
        transcript_text=(
            "AI real estate tools are changing agent workflows. "
            "Listings become content engines. "
            "Lead follow-up gets automated. "
            "Visual presentation becomes the differentiator."
        ),
        segments=[
            TranscriptSegment(0.0, 1.2, "AI real estate tools are changing agent workflows."),
            TranscriptSegment(1.0, 2.4, "Listings become content engines."),
            TranscriptSegment(2.0, 3.2, "Lead follow-up gets automated."),
            TranscriptSegment(2.8, 4.0, "Visual presentation becomes the differentiator."),
        ],
        method="demo_timestamped_transcript",
    )
    out_dir = ROOT / "deliveries" / f"trendscout_source_captioned_clip_pack_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    pack = build_captioned_clip_pack_from_transcripts(
        niche="AI real estate tools",
        transcripts=[transcript],
        output_dir=out_dir,
        orientation="vertical",
        max_clips=4,
    )
    print(out_dir)
    print(pack.to_dict())


if __name__ == "__main__":
    main()
