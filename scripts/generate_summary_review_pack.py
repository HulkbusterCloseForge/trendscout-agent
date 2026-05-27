#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from trendcut_agent.summary_video import SummaryBeat, SummaryVideoPlan, build_summary_video

ROOT = Path(__file__).resolve().parents[1]


def beats_for_ai_real_estate() -> list[SummaryBeat]:
    return [
        SummaryBeat(
            "AI real estate tools: what is changing?",
            "Agents are using AI to compress routine work: listing copy, follow-up messages, lead scoring, and short-form property content.",
            "Summary lens: creator/agency monitoring for AI adoption signals.",
        ),
        SummaryBeat(
            "1. Listings become content engines",
            "One property can turn into listing descriptions, social captions, email blurbs, voiceover scripts, and ad variants.",
            "Why it matters: faster content loops help small brokerages look like full media teams.",
        ),
        SummaryBeat(
            "2. Lead follow-up gets automated",
            "AI assistants can draft replies, summarize buyer intent, and remind agents which prospects need a human touch next.",
            "Watch-out: automation helps speed, but compliance and tone still need review.",
        ),
        SummaryBeat(
            "3. Visuals are the next battleground",
            "Virtual staging, room redesign concepts, and video explainers are becoming differentiators for listings and investor pitches.",
            "Signal: buyers increasingly expect media-rich property stories, not static brochures.",
        ),
        SummaryBeat(
            "Bottom line",
            "The best opportunity is not replacing agents. It is giving agents a repeatable media and follow-up machine around every listing.",
            "TrendScout output: a short summary edit plus audit trail for the chosen niche.",
        ),
    ]


def beats_for_generic_niche() -> list[SummaryBeat]:
    return [
        SummaryBeat(
            "TrendScout turns any niche into a video brief",
            "The user defines an interest. The agent gathers candidate material, ranks what matters, and edits a short explainer video.",
            "Example niches: local cafes, basketball drills, AI tools, founder advice, product launches.",
        ),
        SummaryBeat(
            "The agent looks for signals",
            "It should identify recurring claims, new products, repeated questions, and examples worth showing in the edit.",
            "Audit trail: every run keeps accepted/rejected rationale.",
        ),
        SummaryBeat(
            "The output is a summary, not raw clips",
            "A useful edit explains what is happening, why it matters, and what the viewer should watch next.",
            "This fixes the earlier placeholder issue: no static color cards pretending to be trend edits.",
        ),
        SummaryBeat(
            "Where this goes next",
            "Live sources, Nemotron reasoning, transcript extraction, and stronger media assembly turn this into a recurring creator-ops agent.",
            "MVP target: working local demo first, live integrations second.",
        ),
    ]


def main() -> None:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = ROOT / "deliveries" / f"trendscout_summary_review_pack_{stamp}"
    out_dir.mkdir(parents=True, exist_ok=True)

    videos = [
        SummaryVideoPlan(
            niche="AI real estate tools",
            headline="How AI tools are changing real estate workflows",
            beats=beats_for_ai_real_estate(),
            orientation="vertical",
            seconds_per_beat=4.2,
            output_path=out_dir / "01_ai_real_estate_summary_vertical.mp4",
            source_notes=[{"type": "demo", "note": "Scripted local summary for review; live source retrieval is the next integration."}],
        ),
        SummaryVideoPlan(
            niche="Any user-defined niche",
            headline="TrendScout summary-video mode",
            beats=beats_for_generic_niche(),
            orientation="vertical",
            seconds_per_beat=4.0,
            output_path=out_dir / "02_any_niche_summary_mode_vertical.mp4",
            source_notes=[{"type": "product", "note": "Explains desired product behavior after user feedback."}],
        ),
        SummaryVideoPlan(
            niche="AI real estate tools",
            headline="Horizontal demo for desktop review",
            beats=beats_for_ai_real_estate(),
            orientation="horizontal",
            seconds_per_beat=4.0,
            output_path=out_dir / "03_ai_real_estate_summary_horizontal.mp4",
            source_notes=[{"type": "demo", "note": "Horizontal format variant."}],
        ),
    ]

    rendered = [build_summary_video(plan) for plan in videos]
    (out_dir / "README.md").write_text(
        "# TrendScout Summary Review Pack\n\n"
        "These are corrected demo outputs for the intended product: automatically edited summary videos for a user-defined interest.\n\n"
        "They are silent text-led summary edits, not beep/color placeholder clips. Watch `01_ai_real_estate_summary_vertical.mp4` first.\n\n"
        "## Files\n\n"
        + "\n".join(f"- `{p.name}`" for p in rendered)
        + "\n\n## Product direction\n\n"
        "User-defined interest → source discovery/research → relevance ranking → summary script → edited explainer video → audit trail.\n"
    )
    print(out_dir)


if __name__ == "__main__":
    main()
