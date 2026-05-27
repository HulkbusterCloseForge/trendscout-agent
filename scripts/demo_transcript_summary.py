#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from trendcut_agent.summary_video import SummaryBeat, SummaryVideoPlan, build_summary_video
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
    plan = build_transcript_edit_plan(niche, [transcript])
    beats = [SummaryBeat(i.title, i.summary, i.quote or i.suggested_visual) for i in plan.insights[:5]]
    out_dir = ROOT / "deliveries" / f"trendscout_transcript_summary_demo_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    out_dir.mkdir(parents=True, exist_ok=True)
    output = build_summary_video(SummaryVideoPlan(
        niche=niche,
        headline=plan.headline,
        beats=beats,
        orientation="vertical",
        seconds_per_beat=4.0,
        output_path=out_dir / "transcript_to_summary_demo.mp4",
        source_notes=[{"title": transcript.title, "source_url": transcript.source_url, "method": transcript.method}],
    ))
    (out_dir / "transcript.txt").write_text(DEMO_TRANSCRIPT)
    (out_dir / "nemotron_or_fallback_edit_plan.json").write_text(json.dumps(plan.to_dict(), indent=2))
    (out_dir / "README.md").write_text(
        "# Transcript-to-summary demo\n\n"
        "This demonstrates the intended TrendScout core loop: trending video transcript → Nemotron/fallback decides what matters → summary video.\n\n"
        f"Output: `{output.name}`\n"
    )
    print(out_dir)
    print(output)
    print(plan.provider, plan.model)


if __name__ == "__main__":
    main()
