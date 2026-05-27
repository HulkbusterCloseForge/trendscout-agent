# Contributing

TrendScout Agent is currently a hackathon MVP. Keep changes small, testable, and honest about credential-dependent integrations.

## Local checks

```bash
uv venv .venv
source .venv/bin/activate
uv pip install -e '.[dev]'
python scripts/generate_demo_assets.py
pytest tests -q
python scripts/public_audit.py
python scripts/smoke_run.py
```

## Safety rules

- Do not commit `secrets/`, `data/`, `output/`, `.env`, generated videos, generated audio, or OAuth tokens.
- Do not claim TrendScout generates video; it edits existing source clips.
- Mark Apify, Google, and Nemotron behavior as credential-dependent unless verified in that environment.
- Keep local deterministic demo mode working so judges can run the repo without external accounts.

## Naming note

Public product/repo name: **TrendScout Agent** / `trendscout-agent`.

Internal Python import path remains `trendcut_agent` from the original prototype to avoid a late risky package rename before submission.
