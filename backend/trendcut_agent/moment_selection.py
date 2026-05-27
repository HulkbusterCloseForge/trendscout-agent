from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass

from .llm import _nemotron_chat, llm_status
from .transcript import TranscriptSegment, VideoTranscript


@dataclass
class SelectedMoment:
    transcript_index: int
    start: float
    end: float
    caption: str
    rationale: str
    score: float = 0.5


RUBRIC_START_REJECT = {"and", "but", "because", "so", "which"}
SOFT_MID_SENTENCE_START = RUBRIC_START_REJECT | {"that", "this", "it", "they", "we", "i", "you", "kind", "a", "the"}
PREFERRED_MIN_SECONDS = 10.0
PREFERRED_MAX_SECONDS = 25.0


def _keywords(niche: str) -> set[str]:
    base = {w.lower() for w in re.findall(r"[a-zA-Z][a-zA-Z0-9+-]{2,}", niche)}
    if {"stock", "market"} & base:
        base.update({"stock", "stocks", "market", "markets", "sp500", "s&p", "nasdaq", "dow", "earnings", "rates", "fed", "inflation", "nvidia", "ai", "trend", "trends", "investors", "portfolio"})
    return base


def _keyword_hits(text: str, kws: set[str]) -> list[str]:
    t = text.lower()
    hits = []
    for k in kws:
        if re.search(r"(?<![a-z0-9])" + re.escape(k.lower()) + r"(?![a-z0-9])", t):
            hits.append(k)
    return hits


def _segment_score(text: str, niche: str) -> float:
    t = text.lower()
    kws = _keywords(niche)
    score = 0.0
    keyword_hits = len(_keyword_hits(text, kws))
    score += keyword_hits
    if kws and keyword_hits == 0:
        score -= 3.0
    score += 0.8 if any(ch.isdigit() for ch in t) else 0.0
    score += 0.7 if any(x in t for x in ["important", "trend", "why", "because", "watch", "risk", "opportunity", "right now", "today"]) else 0.0
    words = len(t.split())
    if 6 <= words <= 34:
        score += 1.0
    elif words < 4:
        score -= 1.0
    return score


def heuristic_select_moments(niche: str, transcripts: list[VideoTranscript], max_clips: int = 5) -> list[SelectedMoment]:
    candidates: list[SelectedMoment] = []
    for ti, transcript in enumerate(transcripts):
        for seg in transcript.segments:
            text = " ".join(seg.text.split())
            if not text or len(text.split()) < 3:
                continue
            score = _segment_score(text, niche)
            kws = _keywords(niche)
            if ({"stock", "market"} & kws) and not _keyword_hits(text, kws):
                continue
            duration = max(1.0, (seg.end or seg.start + 5.0) - seg.start)
            # Give context around incomplete transcript chunks, but do not cross
            # into the next segment when the current segment is already a full
            # sentence.
            start = max(0.0, seg.start - 0.15)
            if text.strip()[-1:] in ".!?":
                end = (seg.end + 0.15) if seg.end else start + duration
            else:
                end = max(start + min(6.0, duration + 0.7), seg.end + 0.35 if seg.end else start + 5.0)
            candidates.append(SelectedMoment(
                transcript_index=ti,
                start=start,
                end=end,
                caption=text[:220],
                rationale=f"Heuristic relevance score {score:.2f} for niche '{niche}'.",
                score=score,
            ))
    candidates.sort(key=lambda m: m.score, reverse=True)
    selected: list[SelectedMoment] = []
    seen_captions: set[str] = set()
    for m in candidates:
        key = m.caption.lower().strip()[:80]
        if key in seen_captions:
            continue
        selected.append(m)
        seen_captions.add(key)
        if len(selected) >= max_clips:
            break
    return selected


def _text_starts_mid_sentence(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return False
    first_raw = stripped.split()[0].strip(",;:—- ")
    first = first_raw.lower()
    connector = first in SOFT_MID_SENTENCE_START
    return connector or (first_raw[:1].islower() and first not in {"the", "this"})


def _text_ends_complete(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return False
    return stripped[-1] in ".!?"


def _starts_with_rejected_connector(text: str) -> bool:
    words = text.strip().split()
    if not words:
        return False
    return words[0].lower().strip(",;:—- ") in RUBRIC_START_REJECT


def _rubric_quality_score(text: str) -> float:
    t = text.lower()
    score = 0.0
    score += 1.0 if any(ch.isdigit() for ch in text) else 0.0
    score += 1.0 if any(x in t for x in ["predict", "expect", "risk", "because", "therefore", "means", "will", "could", "should", "watch", "important", "trend", "market", "earnings", "rates"]) else 0.0
    score += 0.7 if text.strip()[-1:] in ".!?" else -1.0
    score -= 2.0 if _starts_with_rejected_connector(text) else 0.0
    return score


def _expand_to_complete_thought(moment: SelectedMoment, transcript: VideoTranscript, *, min_duration: float = PREFERRED_MIN_SECONDS, max_duration: float = PREFERRED_MAX_SECONDS) -> SelectedMoment:
    """Expand a selected timestamp to nearby Whisper segments for complete thoughts.

    Nemotron currently chooses from timestamped Whisper segments. Whisper segments
    often split mid-sentence, so this post-pass expands around the chosen segment
    until the caption reads like a standalone thought.
    """
    segments = transcript.segments
    if not segments:
        return moment
    center = (moment.start + moment.end) / 2.0
    seed = min(range(len(segments)), key=lambda i: abs(((segments[i].start + segments[i].end) / 2.0) - center))
    lo = hi = seed

    def joined() -> str:
        return " ".join(" ".join(s.text.split()) for s in segments[lo:hi + 1]).strip()

    text = joined()
    # If the selection starts mid-sentence, include previous context until it
    # starts like a real sentence boundary or the rubric max duration is hit.
    while lo > 0 and (_text_starts_mid_sentence(text) or segments[lo - 1].text.strip()[-1:] not in ".!?") and (segments[hi].end - segments[lo - 1].start) <= max_duration:
        lo -= 1
        text = joined()
    # Prefer 10–25s clips. Expand forward until the thought is long enough and
    # ends at a sentence boundary, without exceeding the rubric max duration.
    while hi + 1 < len(segments) and ((segments[hi].end - segments[lo].start) < min_duration or not _text_ends_complete(text)) and (segments[hi + 1].end - segments[lo].start) <= max_duration:
        hi += 1
        text = joined()
    # If it still starts with a hard-rejected connector, keep trying previous
    # context. If no prior context exists, the validator can reject it later.
    while lo > 0 and _starts_with_rejected_connector(text) and (segments[hi].end - segments[lo - 1].start) <= max_duration:
        lo -= 1
        text = joined()
    return SelectedMoment(
        transcript_index=moment.transcript_index,
        start=max(0.0, segments[lo].start - 0.15),
        end=max(segments[lo].start + 1.0, segments[hi].end + 0.15),
        caption=text[:420],
        rationale=moment.rationale + " Expanded to nearest complete thought.",
        score=moment.score + _rubric_quality_score(text),
    )


def _passes_editorial_rubric(moment: SelectedMoment, transcript: VideoTranscript | None = None) -> bool:
    duration = moment.end - moment.start
    if transcript and transcript.segments:
        total_duration = max((s.end for s in transcript.segments), default=duration)
    else:
        total_duration = duration
    # For tiny unit-test/demo sources, don't require impossible 10s duration.
    if total_duration >= PREFERRED_MIN_SECONDS and duration < PREFERRED_MIN_SECONDS:
        return False
    if duration > PREFERRED_MAX_SECONDS + 0.25:
        return False
    if _starts_with_rejected_connector(moment.caption):
        return False
    # Sentence boundary: reject lowercase starts that usually indicate we cut
    # into the middle of a sentence/clause.
    first = moment.caption.strip().split()[0].strip(",;:—- ") if moment.caption.strip().split() else ""
    if first[:1].islower():
        return False
    if not _text_ends_complete(moment.caption):
        return False
    return True


def _coerce_moments(value, transcripts: list[VideoTranscript]) -> list[SelectedMoment]:
    if not isinstance(value, list):
        return []
    out: list[SelectedMoment] = []
    for item in value[:8]:
        if not isinstance(item, dict):
            continue
        try:
            ti = int(item.get("transcript_index", 0))
            if ti < 0 or ti >= len(transcripts):
                continue
            start = float(item.get("start", 0.0))
            end = float(item.get("end", start + 6.0))
            caption = str(item.get("caption") or item.get("quote") or "").strip()
            if not caption:
                continue
            moment = SelectedMoment(
                transcript_index=ti,
                start=max(0.0, start),
                end=max(start + 1.0, end),
                caption=caption[:240],
                rationale=str(item.get("rationale") or "Selected by Nemotron."),
                score=float(item.get("score", 0.8)),
            )
            out.append(_expand_to_complete_thought(moment, transcripts[ti]))
        except Exception:
            continue
    return out


def _diversify_moments(moments: list[SelectedMoment], max_clips: int, *, max_per_transcript: int = 3, transcripts: list[VideoTranscript] | None = None) -> list[SelectedMoment]:
    selected: list[SelectedMoment] = []
    per_transcript: dict[int, int] = {}
    seen: set[str] = set()
    rubric_passers = [
        m for m in moments
        if _passes_editorial_rubric(m, transcripts[m.transcript_index] if transcripts and 0 <= m.transcript_index < len(transcripts) else None)
    ]
    pool = rubric_passers or moments
    for moment in sorted(pool, key=lambda m: m.score, reverse=True):
        caption_key = re.sub(r"[^a-z0-9]+", " ", moment.caption.lower()).strip()[:80]
        if caption_key in seen:
            continue
        if per_transcript.get(moment.transcript_index, 0) >= max_per_transcript:
            continue
        selected.append(moment)
        seen.add(caption_key)
        per_transcript[moment.transcript_index] = per_transcript.get(moment.transcript_index, 0) + 1
        if len(selected) >= max_clips:
            return selected
    # If diversity limits left us short, fill from remaining unique moments.
    for moment in sorted(pool, key=lambda m: m.score, reverse=True):
        caption_key = re.sub(r"[^a-z0-9]+", " ", moment.caption.lower()).strip()[:80]
        if caption_key in seen:
            continue
        selected.append(moment)
        seen.add(caption_key)
        if len(selected) >= max_clips:
            break
    return selected


def select_transcript_moments(niche: str, transcripts: list[VideoTranscript], max_clips: int = 5, max_per_transcript: int = 3) -> list[SelectedMoment]:
    """Select clip-worthy timestamped transcript moments.

    Uses Nemotron when configured; otherwise deterministic heuristic scoring.
    Enforces light source diversity so one video does not dominate the pack.
    """
    raw_fallback = heuristic_select_moments(niche, transcripts, max(max_clips * 3, max_clips))
    expanded_fallback = [_expand_to_complete_thought(m, transcripts[m.transcript_index]) for m in raw_fallback]
    fallback = _diversify_moments(expanded_fallback, max_clips, max_per_transcript=max_per_transcript, transcripts=transcripts)
    status = llm_status()
    if status["active_mode"] != "nemotron":
        return fallback
    payload = {
        "task": "Select the most clip-worthy timestamped moments from trending video transcripts for a user-defined niche.",
        "niche": niche,
        "max_clips": max_clips,
        "transcripts": [t.to_dict() for t in transcripts],
        "constraints": [
            "Prefer visually clean, standalone moments that make sense without burned-in captions.",
            "Editorial rubric: clip should be 10-25 seconds, not 4-8 seconds.",
            "Must start at a sentence boundary.",
            "Must end at a sentence boundary.",
            "Reject clips that start with: and, but, because, so, which.",
            "Prefer claims, predictions, risks, numbers, and actionable takes.",
            "One idea per clip.",
            f"Use between 1 and {max_per_transcript} clips per source/transcript.",
        ],
        "schema": {"moments": [{"transcript_index": 0, "start": 0.0, "end": 6.0, "caption": "string", "rationale": "string", "score": 0.9}]},
    }
    try:
        data = _nemotron_chat([
            {"role": "system", "content": "You are TrendScout's clip editor. Return only compact JSON."},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False, default=str)},
        ])
        llm_moments = _coerce_moments(data.get("moments"), transcripts)
        # Nemotron can return too few items or over-focus on one strong source.
        # Merge fallback candidates before diversity limiting so the pack still
        # reaches the requested count with multiple sources when available.
        return _diversify_moments(llm_moments + fallback, max_clips, max_per_transcript=max_per_transcript, transcripts=transcripts) or fallback
    except Exception:
        return fallback
