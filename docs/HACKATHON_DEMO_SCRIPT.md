# Hackathon Demo Script

## 60-second version

1. Open TrendScout dashboard.
2. Show the setup: interest prompt, source, interval, orientation, beat density, Google Drive/Sheet IDs.
3. Show `/api/llm/status` to confirm Nemotron is configured, or explain deterministic fallback for offline judging.
4. Click **Run Live Apify Smoke** or **Run now** for the local deterministic demo.
5. Narrate the pipeline: Plan → Scan → Filter → Edit → Deliver.
6. Open the output video link.
7. Expand run rationale: accepted clips matched the interest; off-interest/duplicate clips are rejected.

## Key lines

- "TrendScout does not generate video. It automates discovery and editing from real scraped source clips."
- "The LLM relevance gate runs twice: before scan to plan the search, and after download to keep off-interest clips out."
- "Beat density lets creators choose every 1, 2, 4, or 8 beats."
- "Delivery lands in Google Drive and Sheets so it fits real creator operations."

## NVIDIA angle

TrendScout uses an OpenAI-compatible NVIDIA/Nemotron endpoint for search planning and post-download relevance verification, with GPU-friendly local media processing for scalable scheduled runs.
