# TrendScout Agent

Hands-off interest scanner that builds beat-matched videos from scraped source clips.

Built for the NVIDIA Agent Challenge as a persistent, deployable long-agent: configure your interests once, run on a schedule, and receive finished beat-match videos in Google Drive with a Google Sheet audit trail. The core planning and relevance gates use NVIDIA Nemotron when configured, with deterministic local fallback for tests and offline demos.

## MVP Promise

TrendScout Agent automatically scans within your interests and delivers a beat-matched video at your chosen interval.

No generative video. TrendScout only uses scraped/downloaded source clips and music/audio supplied by safe demo tracks, user upload, or a configured trend-audio provider.

## Hackathon Fit

- **Autonomous:** runs on an interval without a human in the loop after configuration.
- **Nemotron core reasoning:** `LLM_PROVIDER=nemotron` routes search planning and candidate verification through an OpenAI-compatible NVIDIA/Nemotron endpoint.
- **Real task:** discovers clips, rejects off-brief/duplicate sources, edits to a beat grid, and delivers an audit trail.
- **Persistent/deployable:** FastAPI service + JSON state store + scheduler loop; works locally or on a server.
- **Safe demo mode:** deterministic local clips/audio let judges verify the pipeline without social-platform credentials.

## Pipeline

1. User configures automation options.
2. Agent scans sources for relevant clips.
3. Downloads direct media assets.
4. Uses an LLM relevance gate to keep only content matching the user's interest/spec.
5. Dedupes by source URL and similar audio.
6. Detects the music beat grid.
7. Cuts/assembles source clips to the selected beat density.
8. Uploads the finished MP4 to Google Drive.
9. Logs run settings, source rationale, rejected reasons, and output link to Google Sheets.

## Pre-Automation Options

- Run name
- Interest prompt
- Negative prompt / exclusions
- Source selection: Apify TikTok, YouTube/Shorts, local folder
- Orientation: vertical 9:16 or horizontal 16:9
- Run interval in minutes
- Final video duration
- Target number of source clips
- Beat density: every 1, 2, 4, or 8 beats
- Music source: royalty-free demo track, uploaded audio, or optional trend-audio provider metadata
- Region / market for source discovery
- Strictness: exact, balanced, explore-adjacent
- Auto-widen search when not enough usable clips are found
- Max source age
- Deduping mode: source URL, similar audio, or both
- Processing mode: cloud, local, or auto fallback for editing/analysis only
- Google Drive folder ID
- Google Sheet ID

## NVIDIA / Nemotron Setup

TrendScout defaults to the Nemotron provider interface and falls back to deterministic heuristics only when no API key is present.

```bash
export LLM_PROVIDER=nemotron
export NEMOTRON_API_KEY=...          # or NVIDIA_API_KEY / LLM_API_KEY
export NEMOTRON_MODEL=mistralai/mistral-nemotron
export NVIDIA_BASE_URL=https://integrate.api.nvidia.com/v1
# Optional YouTube source override
export YOUTUBE_SEARCH_QUERY="stock market analysis explainer"
```

Health check:

```bash
curl http://127.0.0.1:8765/api/llm/status
```

The two Nemotron reasoning calls are:

1. `build_search_plan`: turns the user interest into query terms, hashtags, and rejection rules.
2. `verify_candidate`: accepts/rejects each downloaded candidate before it can enter the edit.

## Required Setup

- Apify API token for TikTok/Reels-style discovery/download
- Google OAuth credentials for Drive + Sheets
- ffmpeg installed
- NVIDIA/Nemotron API configuration for relevance decisions

Optional:

- YouTube cookies/downloader configuration for YouTube/Shorts reliability
- Local input folder for deterministic demos


## Deterministic Demo Assets

Generate safe local demo clips and audio:

```bash
python scripts/generate_demo_assets.py
```

Then start the app and click **Run now**. The demo accepts AI/real-estate-related clips, rejects unrelated clips, renders a beat-matched MP4, and writes local Drive/Sheet mock outputs under `output/`.

## Live sourcing smoke

Recommended demo source is YouTube because it usually provides cleaner speech-first videos than TikTok/Reels scraping:

```bash
trendscout run --niche "Stock Market" --source youtube --source-limit 4 --max-clips 6
```

Apify/TikTok remains supported, but can produce music-only or text-baked sources. Important: direct MP4 URLs may point to Apify key-value-store records and require the Apify token when downloading; TrendScout handles this automatically.

## Provider Hooks

### YouTube

TrendScout can use `yt-dlp` search directly, or a URL file override:

```bash
export YOUTUBE_SEARCH_QUERY="stock market analysis explainer"
# optional: one URL per line
export YOUTUBE_URLS_FILE=/path/to/youtube-urls.txt
```

### Apify TikTok

Recommended actor: `clockworks/tiktok-scraper`. See [`docs/APIFY.md`](docs/APIFY.md).


Offline/demo mode:

```bash
export APIFY_TIKTOK_ITEMS_JSON=/path/to/apify-dataset.json
```

Live actor mode:

```bash
export APIFY_API_TOKEN=...
export APIFY_TIKTOK_ACTOR_ID=actor/name-or-id
```

TrendScout extracts direct MP4 URLs from `videoMeta.downloadAddr` or `mediaUrls[0]`.

### Google Drive + Sheets

Preferred dashboard flow:

1. Put the OAuth client JSON at `secrets/google-oauth-client.json` or set `GOOGLE_OAUTH_CLIENT_SECRET_JSON`.
2. Start the app and open the dashboard.
3. Click **Connect Google** and finish consent.
4. Configure a Google Drive folder ID and Google Sheet ID.

The callback saves a refreshable token at `data/google-token.json`. Finished MP4s upload to Drive and run rows append to the `Runs` tab in the configured Sheet.

For simple dev mode, you can also provide:

```bash
export GOOGLE_ACCESS_TOKEN=...
```

Or set `GOOGLE_TOKEN_JSON` to a JSON file containing an access/refresh token. Without Google credentials and IDs, TrendScout uses local mock delivery.

## Hackathon-Safe Audio

Default MVP audio modes:

1. Royalty-free demo track library
2. User-uploaded audio
3. Optional trend-audio metadata mode

Avoid depending on downloading Instagram trending audio for the first public demo.


## Docker

Optional containerized run:

```bash
cp .env.example .env
docker compose up --build
```

Open http://127.0.0.1:8765. Runtime state is mounted to `data/`, `output/`, and `samples/`.

## Run Locally

Raw commands, no Make required:

```bash
cd trendscout-agent
uv venv .venv
source .venv/bin/activate
uv pip install -e '.[dev]'
python scripts/generate_demo_assets.py
pytest tests -q
uvicorn trendcut_agent.app:app --host 127.0.0.1 --port 8765 --reload
```

Then open http://127.0.0.1:8765 and click **Run now**.

Make shortcuts, if `make` is installed:

```bash
cd trendscout-agent
make setup
make demo
make run
```

If you prefer raw commands:

```bash
uv venv .venv
source .venv/bin/activate
uv pip install -e '.[dev]'
python scripts/generate_demo_assets.py
uvicorn trendcut_agent.app:app --host 127.0.0.1 --port 8765 --reload
```

Open http://127.0.0.1:8765.

Run the deterministic CLI smoke test with `make smoke`. Before publishing, run `make audit` to check for obvious token leaks.

For a deterministic demo, place a few `.mp4`/`.mov` files in `samples/inbox/`. If no audio is provided, TrendScout creates a hackathon-safe generated demo beat track.

## Relevance Filtering

TrendScout uses two relevance gates:

1. **Pre-scan planning gate**: turns the interest prompt/exclusions into search terms, hashtags, and rejection rules.
2. **Post-download verification gate**: checks downloaded candidate metadata/sidecars before any clip can enter the edit.

This protects the main failure case: outputting clips outside the user's interest.

## CI / Verification

The repo includes `.github/workflows/ci.yml` for GitHub Actions. It installs ffmpeg, installs the package, runs tests, runs the public token audit, generates deterministic demo assets, and performs a smoke run.

Local equivalent:

```bash
pytest tests -q
python scripts/public_audit.py
python scripts/generate_demo_assets.py
python scripts/smoke_run.py
```

See `docs/DEMO_RECORDING_RUNBOOK.md` for the demo recording checklist.

## Submission Fields

- **Team name:** CultureCraft / Hulkbuster
- **Project name:** TrendScout Agent
- **Project description:** A persistent Nemotron-powered long agent that scans creator niches, finds relevant source clips, rejects off-brief or duplicate candidates, beat-matches accepted clips to safe audio, and delivers MP4 outputs plus an audit trail to Drive/Sheets.
- **Tools used:** NVIDIA Nemotron/NIM-compatible LLM endpoint, Python, FastAPI, ffmpeg, Apify TikTok scraper, Google Drive API, Google Sheets API, pytest.
- **NemoClaw:** Not used in this MVP; architecture leaves room for policy guardrails around source access, platform rules, and delivery destinations.

## Limitations

- The public demo uses local generated clips unless Apify/Google/Nemotron credentials are supplied.
- TrendScout edits existing clips; it does not generate video.
- Platform scraping/downloading must follow the operator's API/provider terms and permissions.
- Google delivery requires OAuth setup; otherwise local mock Drive/Sheet outputs are written under `output/`.

## Status

Submission-ready MVP: configure options → run scheduled or manual job → create beat-matched MP4 → upload/mock Drive → append/mock Sheet row → show run history and rationale.
