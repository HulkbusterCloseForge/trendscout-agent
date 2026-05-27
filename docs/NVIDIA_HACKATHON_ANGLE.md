# NVIDIA Hackathon Angle

TrendScout Agent is a persistent long-agent for creator operations. It does not generate video; it automates the repetitive work around trend discovery, relevance filtering, beat editing, and delivery.

## Problem

Creators and agencies waste hours finding on-brief clips, rejecting irrelevant duplicates, cutting them to music, and logging what was used. This is especially painful for recurring user-defined niches like local business promos, education snippets, sports drills, market monitoring, or AI tools.

## Solution

TrendScout runs autonomously on a schedule:

1. Build a source-search plan from the user’s interest.
2. Discover/download candidate clips from configured sources.
3. Use Nemotron to verify each candidate against the brief and exclusions.
4. Dedupe by source URL/audio/account.
5. Detect a beat grid from safe audio.
6. Assemble a vertical or horizontal beat-matched MP4 with ffmpeg.
7. Deliver to Google Drive and append an audit row to Google Sheets.

## How It Uses NVIDIA / Nemotron

The core reasoning layer is in `backend/trendcut_agent/llm.py`.

- `build_search_plan(...)` calls an OpenAI-compatible NVIDIA/Nemotron endpoint to produce:
  - query
  - keywords
  - hashtags
  - rejection rules
  - whether to widen search
- `verify_candidate(...)` calls Nemotron again after source discovery to decide:
  - accepted/rejected
  - confidence
  - rationale
  - matched terms
  - whether the agent should widen search

Configuration:

```bash
export LLM_PROVIDER=nemotron
export NEMOTRON_API_KEY=...
export NEMOTRON_MODEL=mistralai/mistral-nemotron
export NVIDIA_BASE_URL=https://integrate.api.nvidia.com/v1
```

`GET /api/llm/status` exposes whether the service is using Nemotron or deterministic fallback.

The deterministic fallback exists so reviewers can run tests and the local demo without paid credentials. For the actual challenge deployment, Nemotron should be configured.

## NVIDIA Fit

- **Long-agent behavior:** persistent scheduler loop, saved config/history, recurring autonomous execution.
- **Nemotron core reasoning:** source planning and relevance verification are model-driven gates.
- **GPU/media fit:** production deployments can use NVIDIA hardware for fast local decode/transcode/analysis while the current MVP keeps ffmpeg portable.
- **Real workflow:** produces usable videos and an audit trail, not just a chatbot or slide demo.

## Demo Script

1. Open dashboard.
2. Configure any user-defined niche, for example `AI real estate tools`, `Taiwan cafe openings`, or `basketball training drills`.
3. Choose vertical, every 2 beats, 8 seconds, local demo or Apify source.
4. Show `/api/llm/status` with Nemotron configured when available.
5. Click **Run Now**.
6. Show accepted/rejected rationale.
7. Open output MP4.
8. Open Sheet mock / Google Sheet row.

## Avoid Saying

- Do not claim TrendScout generates video.
- Do not depend on scraped Instagram audio for the demo.
- Do not promise auto-posting.

## Submission Summary

TrendScout is a Nemotron-powered autonomous editing operator: it repeatedly scans a niche, reasons over candidate relevance, turns approved source clips into beat-matched edits, and leaves a delivery/audit trail ready for creator teams.
