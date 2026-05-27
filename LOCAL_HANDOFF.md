# TrendScout Agent — Local Handoff

## Current status

Local MVP is ready for demo/submission prep. Nothing has been pushed or submitted externally.

## Canonical local paths

- Working project: `/home/hulkb/.openclaw/workspace/trendcut-agent` (folder name is old; product/repo name is TrendScout)
- Clean public repo export: `/tmp/trendscout-agent-public`
- Clean public tarball: `/tmp/trendscout-agent-public.tar.gz`
- Submission packet: `docs/SUBMISSION_PACKET.md`
- Demo recording runbook: `docs/DEMO_RECORDING_RUNBOOK.md`

## Verification completed

Main working tree:

- `pytest tests -q` → 14 passed
- `python scripts/public_audit.py` → passed
- `python scripts/generate_demo_assets.py && python scripts/smoke_run.py` → produced local demo MP4 + mock sheet
- `docker build -t trendscout-agent:local .` → passed

Clean tarball/export test:

- Extracted `/tmp/trendscout-agent-public.tar.gz` into `/tmp/trendscout-clean-test`
- Created fresh venv with `uv`
- Installed package from clean export
- `pytest tests -q` → 14 passed
- `python scripts/public_audit.py` → passed
- `python scripts/generate_demo_assets.py && python scripts/smoke_run.py` → completed
- Clean test output MP4: `/tmp/trendscout-clean-test/output/drive_mock/20260527T063309Z_2da916e8_trendscout.mp4`
- Clean test mock sheet: `/tmp/trendscout-clean-test/output/trendscout_sheet_mock.csv`

Final clean public export:

- Git branch: `main`
- Local commit: `fb2347d`
- Tracked files: 44
- Tarball size: 207 KB
- Docker image built locally: `trendscout-agent:local`
- Secrets/data/output/media excluded

## Added while Roger was away

- `Dockerfile`
- `docker-compose.yml`
- `.dockerignore`
- `.github/workflows/ci.yml`
- `CONTRIBUTING.md`
- `docs/DEMO_RECORDING_RUNBOOK.md`
- README sections for Docker and CI/verification

## Product truth

Ready as:

- local MVP
- hackathon demo candidate
- repository submission package after GitHub push
- container-buildable local service

Not yet done:

- GitHub remote creation/push
- real Nemotron credential verification
- live Apify run proof
- real Google Drive/Sheets OAuth proof
- recorded demo video URL

## How to run locally

```bash
cd /home/hulkb/.openclaw/workspace/trendcut-agent
source .venv/bin/activate
python scripts/generate_demo_assets.py
pytest tests -q
python scripts/public_audit.py
uvicorn trendcut_agent.app:app --host 127.0.0.1 --port 8765 --reload
```

Open: `http://127.0.0.1:8765`

## Docker run

```bash
cd /home/hulkb/.openclaw/workspace/trendcut-agent
cp .env.example .env
docker compose up --build
```

Open: `http://127.0.0.1:8765`

## Nemotron env

```bash
export LLM_PROVIDER=nemotron
export NEMOTRON_API_KEY=...
export NEMOTRON_MODEL=nvidia/llama-3.1-nemotron-ultra-253b-v1
export NVIDIA_BASE_URL=https://integrate.api.nvidia.com/v1
```

Status endpoint:

```bash
curl http://127.0.0.1:8765/api/llm/status
```

## Tomorrow actions

1. Repo/product name selected: `trendscout-agent` / TrendScout Agent.
2. Provide GitHub auth or create empty repo URL.
3. Push `/tmp/trendscout-agent-public` only.
4. Record short demo from local dashboard using `docs/DEMO_RECORDING_RUNBOOK.md`.
5. Fill Airtable using `docs/SUBMISSION_PACKET.md`.

## Do not accidentally publish

Do **not** push `/home/hulkb/.openclaw/workspace` as a repo. It contains unrelated workspace files. Only push `/tmp/trendscout-agent-public` or a fresh export created from the working project with excludes.
