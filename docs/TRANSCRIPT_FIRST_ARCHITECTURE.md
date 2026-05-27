# Transcript-first TrendScout Architecture

Roger's correction: the product should not just stitch clips to a beat, and it should not output one combined summary video. The core product is:

**user-defined interest → trending videos → transcripts → Nemotron importance analysis → separate captioned clips**

## Target pipeline

1. **Niche input**
   - User defines any niche/topic.
   - Examples: `AI real estate tools`, `Taiwan cafe openings`, `basketball training drills`.

2. **Trend/source discovery**
   - Query live source providers for top/trending videos in that niche.
   - Initial provider: Apify TikTok scraper hook.
   - Future providers: YouTube Shorts, Instagram/Reels provider, RSS/news/video sources.

3. **Download source videos**
   - Download the most relevant/trending candidate videos.
   - Keep metadata: source URL, author, caption, engagement, publish date.

4. **Transcript extraction**
   - Prefer provider captions/transcripts when available.
   - Fall back to audio transcription (Whisper/OpenAI or local ASR).
   - Store transcript text and timestamped segments.

5. **Nemotron transcript intelligence**
   - Nemotron receives transcripts + source metadata.
   - It identifies:
     - key claims
     - surprising or high-signal moments
     - repeated patterns across videos
     - useful quotes/segments
     - what to skip
     - suggested captions and visual treatment

6. **Clip plan**
   - Convert Nemotron output into a structured clip pack:
     - hook clip
     - 3–5 standalone insight clips
     - source quote/segment reference
     - captions for each clip
     - rationale/importance score

7. **Clip pack export**
   - Output is **multiple short clips**, not one summary montage.
   - Each clip has a manifest entry and `.srt` caption sidecar.
   - Burned-in captions are optional and default OFF because they can clutter source clips.
   - MVP: cut actual source video segments from selected transcript moments.
   - Later: optional music bed, beat pacing, burned captions, narration, and platform-specific formatting.

8. **Audit trail / review queue**
   - Save transcript, clip plan, source metadata, selected/skipped rationale, and per-clip output links.
   - Human can approve/reject clips before posting or delivery.

## Implemented scaffold

- `backend/trendcut_agent/transcript.py`
  - audio extraction helper
  - sidecar/provider transcript loader
  - transcript data structures

- `backend/trendcut_agent/transcript_intelligence.py`
  - `build_transcript_edit_plan(...)`
  - uses Nemotron when credentials are configured
  - deterministic fallback for local tests/demo

- `backend/trendcut_agent/captioned_clips.py`
  - builds a folder of separate clip MP4s
  - writes `clip_pack_manifest.json`
  - writes `.srt` caption sidecars
  - supports optional burned-in captions via `--burn-captions`, default OFF

- `backend/trendcut_agent/summary_video.py`
  - low-level text-card renderer reused by the captioned clip MVP

- `scripts/demo_transcript_clips.py`
  - demonstrates transcript → edit plan → multiple captioned clips

- `scripts/demo_transcript_summary.py`
  - legacy demo; useful for comparison only, not the target product output

## Product positioning update

Transcript intelligence and captioned clip packs are the product core. Beat matching and one-piece summary montage are optional styles, not the default output.
