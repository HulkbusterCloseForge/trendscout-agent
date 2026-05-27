# TrendScout Agent MVP Spec

## Product Definition

TrendScout Agent is a scheduled automation tool that creates beat-matched videos from scraped source clips matching a user's interests.

It does not generate video. It edits downloaded/scraped clips into music-synced montages.

## Success Metric

Time saved: the user configures interests/options once and receives finished beat-matched videos automatically at each interval.

## Non-Goals for MVP

- No social auto-posting
- No approval workflow
- No video generation models
- No Replicate requirement
- No ComfyUI/Wan requirement
- No brand profile learning
- No performance feedback loop

## Core User Flow

1. User opens dashboard.
2. User configures automation:
   - interest prompt
   - exclusions
   - source(s)
   - interval
   - vertical/horizontal
   - final duration
   - beat density: 1/2/4/8
   - music source
   - Google Drive folder
   - Google Sheet
3. User starts automation.
4. Server runs every configured interval while open/running.
5. Each run produces:
   - one beat-matched MP4 in Google Drive
   - one Google Sheet row with run details and rationale
   - visible dashboard history

## Source Priority

1. Local folder for reliable demo input
2. Apify TikTok direct MP4 URLs
3. YouTube/Shorts via downloader
4. Instagram/Reels via Apify/provider later if stable

## Relevance Gate

LLM receives:
- user interest prompt
- negative prompt
- candidate metadata/transcript/caption
- strictness level
- current accepted count

LLM returns:
- accept/reject
- confidence
- rationale
- whether to widen search

Primary failure to avoid: clips outside user interest.

## Beat Matching

Song/audio is timing master.

User selects beat density:
- 1 = cut/place on every beat
- 2 = every 2 beats
- 4 = every 4 beats
- 8 = every 8 beats

The editor should:
- detect tempo/beat grid/percussive onsets
- choose clips to fit intervals
- cut on beat boundaries
- avoid repetitive clips
- render final MP4 in selected orientation

## Sheet Logging

Each run appends:
- timestamp
- run name
- config snapshot
- source query
- accepted source URLs
- rejected source URLs and reasons
- dedupe decisions
- beat density
- audio used
- Drive output URL
- errors/warnings
