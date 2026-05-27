#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from trendcut_agent.captioned_clips import build_captioned_clip_pack_from_plan
from trendcut_agent.transcript import VideoTranscript
from trendcut_agent.transcript_intelligence import build_transcript_edit_plan

ROOT = Path(__file__).resolve().parents[1]

DEMO_TRANSCRIPT = """
AI real estate tools are changing the daily workflow for agents. The first big shift is listing content: one property can become a description, Instagram caption, email campaign, ad copy, and a short video script in minutes. The second shift is lead follow-up. AI assistants can summarize buyer intent, draft replies, and remind the agent which prospects need attention. The third shift is visual presentation. Virtual staging, renovation previews, and property explainer videos help listings stand out. But the risk is over-automation: agents still need to check compliance, fair housing language, and local accuracy. The opportunity is not replacing agents; it is giving every agent a small media and operations team around each listing.
""".strip()


def main() -> None:
    niche = "AI real estate tools"
    transcript = VideoTranscript(
        source_path="demo://trending-video",
        source_url="demo://trending-video",
        title="Demo trending video transcript",
        transcript_text=DEMO_TRANSCRIPT,
        method="demo_transcript",
    )
    edit_plan = build_transcript_edit_plan(niche, [transcript])
    out_dir = ROOT / "deliveries" / f"trendscout_captioned_clip_pack_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    pack = build_captioned_clip_pack_from_plan(
        niche=niche,
        edit_plan=edit_plan,
        output_dir=out_dir,
        orientation="vertical",
        seconds_per_clip=4.0,
    )
    (out_dir / "source_transcript.txt").write_text(DEMO_TRANSCRIPT)
    (out_dir / "nemotron_or_fallback_edit_plan.json").write_text(json.dumps(edit_plan.to_dict(), indent=2))
    print(out_dir)
    print(json.dumps(pack.to_dict(), indent=2))


if __name__ == "__main__":
    main()
