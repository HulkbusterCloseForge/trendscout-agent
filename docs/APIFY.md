# Apify Source Setup

Recommended MVP actor: `clockworks/tiktok-scraper`.

Why this actor:

- Large usage base and active maintenance.
- Supports search queries, hashtags, profiles, posts, URLs, and music/video metadata.
- Known output shape includes direct media fields used by TrendScout: `videoMeta.downloadAddr` or `mediaUrls[0]`.

## Environment

```bash
export APIFY_API_TOKEN="..."
export APIFY_TIKTOK_ACTOR_ID="clockworks/tiktok-scraper"
export APIFY_RESULTS_LIMIT=40
```

Optional offline mode using a saved dataset export:

```bash
export APIFY_TIKTOK_ITEMS_JSON=/path/to/apify-items.json
```

Offline mode is preferred for hackathon rehearsals because it is deterministic and avoids live scraping failures.

## Actor Input

TrendScout sends a generic input by default:

```json
{
  "searchQueries": ["<LLM search plan query>"],
  "resultsPerPage": 20,
  "maxItems": 40,
  "shouldDownloadVideos": true,
  "shouldDownloadCovers": false,
  "shouldDownloadSubtitles": false
}
```

You can override or extend this with:

```bash
export APIFY_TIKTOK_ACTOR_INPUT_JSON='{"maxItems": 20}'
```

## Media Routing Rule

Never route TikTok page URLs as media assets. TrendScout downloads source clips from:

1. `videoMeta.downloadAddr`
2. fallback `mediaUrls[0]`

The TikTok page URL is kept only for logging/attribution/debugging.

## Cost note

TrendScout sets `shouldDownloadVideos: true` because the editor needs actual MP4 files. Keep `APIFY_RESULTS_LIMIT` small during tests. The live smoke used `maxItems: 5` and produced downloadable MP4 candidates.

## Dashboard demo button

When `APIFY_API_TOKEN` or `APIFY_TIKTOK_ITEMS_JSON` is configured, the dashboard shows a **Run Live Apify Smoke** button. It uses the current interest/options, switches source mode to Apify TikTok, runs one job, and records accepted/rejected rationale in history.
