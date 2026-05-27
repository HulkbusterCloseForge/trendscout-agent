from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any

from .llm import _nemotron_chat, llm_status
from .transcript import VideoTranscript


@dataclass
class TranscriptInsight:
    title: str
    summary: str
    importance: float = 0.5
    suggested_visual: str = ""
    quote: str = ""


@dataclass
class TranscriptEditPlan:
    niche: str
    headline: str
    thesis: str
    insights: list[TranscriptInsight] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    provider: str = "heuristic"
    model: str = "local-heuristic"

    def to_dict(self) -> dict:
        data = asdict(self)
        data["insights"] = [asdict(i) for i in self.insights]
        return data


def _sentences(text: str) -> list[str]:
    normalized = " ".join(text.replace("\n", " ").split())
    parts: list[str] = []
    cur = ""
    for ch in normalized:
        cur += ch
        if ch in ".!?" and len(cur.strip()) > 25:
            parts.append(cur.strip())
            cur = ""
    if cur.strip():
        parts.append(cur.strip())
    return parts


def heuristic_transcript_plan(niche: str, transcripts: list[VideoTranscript]) -> TranscriptEditPlan:
    combined = "\n".join(t.transcript_text for t in transcripts if t.transcript_text).strip()
    sentences = _sentences(combined)
    if not sentences and combined:
        sentences = [combined]
    picks = sentences[:5]
    insights = []
    for idx, sentence in enumerate(picks, 1):
        insights.append(TranscriptInsight(
            title=f"Point {idx}",
            summary=sentence[:260],
            importance=max(0.45, 0.9 - idx * 0.08),
            suggested_visual="Use the source segment or a text-led summary card.",
            quote=sentence[:180],
        ))
    if not insights:
        insights = [TranscriptInsight("No transcript found", "Add captions/transcripts or enable Whisper before summarization.", 0.2)]
    return TranscriptEditPlan(
        niche=niche,
        headline=f"What matters in {niche}",
        thesis=f"A short summary of the most important points found in trending source transcripts for {niche}.",
        insights=insights,
        provider="heuristic",
        model="local-heuristic",
    )


def _coerce_insights(value: Any) -> list[TranscriptInsight]:
    if not isinstance(value, list):
        return []
    out: list[TranscriptInsight] = []
    for item in value[:7]:
        if not isinstance(item, dict):
            continue
        try:
            out.append(TranscriptInsight(
                title=str(item.get("title") or "Insight"),
                summary=str(item.get("summary") or ""),
                importance=float(item.get("importance", 0.5)),
                suggested_visual=str(item.get("suggested_visual") or ""),
                quote=str(item.get("quote") or ""),
            ))
        except Exception:
            continue
    return out


def build_transcript_edit_plan(niche: str, transcripts: list[VideoTranscript]) -> TranscriptEditPlan:
    """Use Nemotron to decide what matters in trending-video transcripts.

    Falls back to deterministic extraction when credentials are unavailable so
    the repo remains runnable for reviewers.
    """
    fallback = heuristic_transcript_plan(niche, transcripts)
    status = llm_status()
    if status["active_mode"] != "nemotron":
        return fallback

    payload = {
        "task": "Given transcripts from trending videos for a user-defined niche, decide what is important and produce a short summary-video edit plan.",
        "niche": niche,
        "transcripts": [t.to_dict() for t in transcripts],
        "schema": {
            "headline": "string",
            "thesis": "string",
            "insights": [{"title": "string", "summary": "string", "importance": "0..1", "suggested_visual": "string", "quote": "string"}],
            "skipped": ["string"],
        },
    }
    try:
        data = _nemotron_chat([
            {"role": "system", "content": "You are TrendScout's transcript intelligence editor. Return only compact JSON."},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False, default=str)},
        ])
        insights = _coerce_insights(data.get("insights")) or fallback.insights
        skipped = [str(x) for x in data.get("skipped", [])[:10]] if isinstance(data.get("skipped"), list) else []
        return TranscriptEditPlan(
            niche=niche,
            headline=str(data.get("headline") or fallback.headline),
            thesis=str(data.get("thesis") or fallback.thesis),
            insights=insights,
            skipped=skipped,
            provider="nemotron",
            model=status["model"],
        )
    except Exception as exc:
        fallback.provider = "heuristic_fallback"
        fallback.model = f"local-heuristic; nemotron_error={str(exc)[:180]}"
        return fallback
