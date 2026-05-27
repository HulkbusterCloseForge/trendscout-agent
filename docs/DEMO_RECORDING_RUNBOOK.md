# Demo Recording Runbook

Goal: record a clean 60–120 second demo for the NVIDIA Agent Challenge without requiring live third-party credentials.

## Recommended demo niche

Use any user-defined niche. Good examples:

- `AI real estate tools`
- `Taiwan cafe openings`
- `basketball training drills`
- `B2B SaaS founder tips`

The deterministic sample assets currently match `AI real estate tools`, so use that for the safest local recording unless you add new sample clips/sidecars.

## Preflight

```bash
cd /home/hulkb/.openclaw/workspace/trendcut-agent
source .venv/bin/activate
python scripts/generate_demo_assets.py
pytest tests -q
python scripts/public_audit.py
python scripts/smoke_run.py
```

Expected: tests pass, audit passes, and `scripts/smoke_run.py` prints an MP4 path and mock sheet path.

## Start dashboard

```bash
uvicorn trendcut_agent.app:app --host 127.0.0.1 --port 8765 --reload
```

Open: `http://127.0.0.1:8765`

## Shots to capture

1. Dashboard title: **TrendScout Agent**.
2. Automation setup controls:
   - interest prompt
   - exclusions
   - source
   - interval
   - orientation
   - beat density
   - delivery settings
3. LLM status:
   - show `/api/llm/status`
   - say Nemotron is used when credentials are configured; local demo uses deterministic fallback.
4. Click **Run now**.
5. Show run history/rationale:
   - accepted clips
   - rejected/off-interest clips
   - output path/link
6. Open rendered MP4.
7. Open mock sheet CSV or real Google Sheet if OAuth is configured.

## 60-second narration

"TrendScout Agent is for creators and agencies who repeatedly need niche trend edits. A human defines any niche once — for example AI real estate tools, local cafes, or basketball drills — and the agent handles the recurring workflow: plan, scan, filter, edit, and deliver. With Nemotron credentials configured, TrendScout uses NVIDIA/Nemotron for search planning and post-download relevance verification. In this local demo, deterministic fallback keeps the repo runnable for judges. The output is a beat-matched MP4 from existing source clips, plus an audit trail showing why clips were accepted or rejected."

## Keep claims honest

- Say it edits existing source clips, not generated video.
- Say live Apify, Google Drive/Sheets, and real Nemotron require credentials.
- Say local deterministic demo works without external accounts.
