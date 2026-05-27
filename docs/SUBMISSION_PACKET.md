# TrendScout Agent — Submission Packet

## Airtable-style submission answers

**Team name**  
CultureCraft / Hulkbuster

**Project name**  
TrendScout Agent

**One-line summary**  
TrendScout Agent is a scheduled creator-ops agent that scans a niche, filters source clips for relevance, beat-matches approved clips to safe audio, and delivers an MP4 plus an audit trail.

**Project description**  
Creators and agencies waste hours finding on-brief clips, rejecting irrelevant duplicates, cutting clips to music, and logging what was used. TrendScout turns that repeated workflow into an autonomous long-agent: configure the interest, exclusions, source, interval, orientation, beat density, audio, and delivery targets once; each run plans a search, discovers/downloads candidate clips, verifies relevance, dedupes, renders a beat-matched edit, and records the result.

**What it does today**  
- Runs as a local FastAPI dashboard/service.
- Supports deterministic local demo clips and generated safe demo audio.
- Supports an Apify TikTok source hook when an Apify token or offline dataset is configured.
- Renders beat-matched MP4s with ffmpeg.
- Writes local mock Drive/Sheet outputs when Google OAuth is not configured.
- Can upload/append to Google Drive/Sheets when OAuth credentials and target IDs are supplied.
- Stores config/history so it can operate on a schedule while the service is running.

**NVIDIA / Nemotron usage**  
TrendScout has a Nemotron-compatible reasoning adapter in `backend/trendcut_agent/llm.py`. When `LLM_PROVIDER=nemotron` and valid NVIDIA/Nemotron credentials are configured, it calls an OpenAI-compatible NVIDIA/Nemotron endpoint for:
1. `build_search_plan` — query terms, hashtags, rejection rules, and widening strategy.
2. `verify_candidate` — accept/reject, confidence, rationale, matched terms, and widening decision.

The local MVP also includes deterministic fallback logic so judges can run the demo and tests without credentials. Real Nemotron execution requires valid NVIDIA/Nemotron API credentials.

**Tools / technologies used**  
NVIDIA/Nemotron-compatible LLM endpoint adapter, Python, FastAPI, ffmpeg, Apify TikTok scraper hook, Google Drive API, Google Sheets API, pytest, local JSON state.

**Target user**  
Creators, social teams, and agencies that repeatedly produce niche trend/research montages for business content, education, local promotion, or market monitoring.

**Why it matters**  
It removes the repetitive middle work between “find clips about this niche” and “deliver a usable beat edit with a source log.” The product is not another chatbot; it is an operator that performs a concrete recurring media workflow.

**Autonomy / long-agent behavior**  
TrendScout saves user configuration, runs manually or on a schedule, tracks run state/history, retries through source widening when enabled, and outputs a finished artifact plus accepted/rejected rationales.

**Demo path**  
1. Generate deterministic demo assets.
2. Open the dashboard.
3. Show the configured interest, source, beat density, delivery settings, and LLM status.
4. Click **Run now** or **Run Live Apify Smoke** if credentials/dataset are available.
5. Show accepted/rejected rationale.
6. Open the rendered MP4 and mock/real Sheet log.

**Honest limitations**  
- TrendScout edits existing source clips; it does not generate video.
- Real Nemotron calls require credentials and endpoint configuration.
- Real Google Drive/Sheets delivery requires OAuth setup; otherwise local mocks are used.
- Live Apify sourcing requires a token or offline dataset.
- No auto-posting in the MVP.
- Platform sourcing must follow provider/API terms and operator permissions.

**Repository status**  
Submission-ready local MVP: configure options → run scheduled/manual job → create beat-matched MP4 → mock/upload Drive output → mock/append Sheet row → show run history and rationale.

## 60-second demo script

**0:00–0:08 — Problem**  
“TrendScout is for creators and agencies who repeatedly need niche trend edits. The pain is not generating video — it is finding on-brief clips, rejecting junk, cutting to music, and logging sources.”

**0:08–0:20 — Setup**  
“Here is the dashboard. I set the interest to any user-defined niche, for example `AI real estate tools`, choose local demo or Apify TikTok, vertical format, every 2 beats, target duration, and Drive/Sheet delivery.”

**0:20–0:30 — Nemotron gate**  
“This status endpoint shows whether the Nemotron adapter is configured. With credentials, TrendScout uses Nemotron for search planning and candidate verification. Without credentials, the local demo uses deterministic fallback so judges can still run it.”

**0:30–0:45 — Run**  
“I click Run now. The agent plans, scans, filters, dedupes, beat-matches with ffmpeg, and delivers the output.”

**0:45–0:60 — Result**  
“Here is the finished MP4, and here is the audit trail: accepted clips matched the brief, rejected clips were off-interest or duplicates. This is a recurring creator-ops agent, not a one-off prompt.”

## 2-minute demo script

**0:00–0:15 — Frame the workflow**  
“TrendScout Agent automates the repetitive creator operations around short-form edits. A human configures the niche once; the agent repeatedly finds relevant source clips, filters them, beat-matches them, and delivers both the video and an audit log.”

**0:15–0:35 — Dashboard configuration**  
“On the dashboard I configure run name, interest prompt, exclusions, source, interval, orientation, duration, target source count, beat density, audio mode, region, dedupe mode, and delivery IDs. The MVP supports local deterministic clips for judging, an Apify TikTok hook for live sourcing, and Google Drive/Sheets when OAuth is connected.”

**0:35–0:55 — NVIDIA / Nemotron role**  
“The reasoning layer lives in `backend/trendcut_agent/llm.py`. With `LLM_PROVIDER=nemotron`, a valid API key, model, and NVIDIA base URL, TrendScout calls Nemotron twice: first to build the search plan, then after discovery to verify each candidate before it can enter the edit. The fallback path exists only so the local demo and tests are runnable without paid credentials.”

**0:55–1:20 — Run the agent**  
“I click Run now. The current run moves through Plan, Scan, Filter, Edit, and Deliver. The relevance gate keeps the main failure case out: clips that are popular but unrelated to the user's actual niche.”

**1:20–1:40 — Show output**  
“TrendScout renders an MP4 from existing clips; it does not generate video. The beat density controls cuts every 1, 2, 4, or 8 beats. For public judging, the local demo uses safe generated assets and audio.”

**1:40–2:00 — Show audit trail and close**  
“The run history shows accepted and rejected clips with rationales, plus the output video link and Sheet/log link. In production this fits a creator team's recurring workflow: configure once, run on schedule, receive finished videos and source accountability.”

## Judging checklist

- [ ] Dashboard opens locally at `http://127.0.0.1:8765`.
- [ ] `GET /api/llm/status` clearly reports Nemotron configured vs deterministic fallback.
- [ ] Submission wording does not claim video generation.
- [ ] Submission wording says real Nemotron requires credentials.
- [ ] Local deterministic demo assets can be generated.
- [ ] Manual **Run now** completes with a rendered MP4.
- [ ] Run history shows accepted and rejected rationales.
- [ ] Beat density option is visible: 1, 2, 4, 8 beats.
- [ ] Local mock Drive/Sheet outputs are created when Google is not configured.
- [ ] Google OAuth path is documented as optional for real Drive/Sheets delivery.
- [ ] Apify live smoke is presented as credential/dataset-dependent.
- [ ] README and docs agree on limitations and MVP status.
- [ ] Tests pass before final upload.
- [ ] `make audit` or equivalent public audit passes before sharing.
- [ ] No secrets are committed or pasted into submission fields.

## Tomorrow push checklist

1. **Fresh run from clean shell**
   - `cd trendscout-agent`
   - Activate venv / install if needed.
   - `python scripts/generate_demo_assets.py`
   - `pytest tests -q`
   - `make audit` if `make` is available.

2. **Record or rehearse demo**
   - Start app: `uvicorn trendcut_agent.app:app --host 127.0.0.1 --port 8765 --reload`
   - Open dashboard.
   - Show `/api/llm/status`.
   - Run deterministic demo.
   - Open MP4 and Sheet/log output.

3. **Submission copy sanity check**
   - Use the Airtable answers above.
   - Keep claims honest: local MVP works; Nemotron adapter path exists; real Nemotron requires credentials.
   - Avoid “auto-posting,” “video generation,” or “Instagram trending audio” claims.

4. **Repo/package check**
   - Confirm `.gitignore` excludes secrets, tokens, generated local state as intended.
   - Confirm demo output path exists and is easy to open.
   - Confirm `README.md`, `docs/HACKATHON_DEMO_SCRIPT.md`, and this packet do not conflict.

5. **Final submit**
   - Paste concise answers.
   - Attach/demo-link the local recording if required.
   - Include repo link if requested.
   - Mention credentials-dependent integrations plainly.
