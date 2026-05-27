#!/usr/bin/env python3
from __future__ import annotations

import os
from pathlib import Path

from trendcut_agent.config import AutomationConfig, SourceType
from trendcut_agent.runner import TrendCutRunner
from trendcut_agent.store import JsonStore

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUTPUT = ROOT / "output"


def main() -> None:
    # Reset local demo state so smoke is repeatable.
    if (OUTPUT / "dedupe.json").exists():
        (OUTPUT / "dedupe.json").unlink()
    store = JsonStore(DATA)
    cfg = AutomationConfig(
        run_name="TrendScout Smoke Demo",
        interest_prompt="AI real estate tools",
        exclusions="restaurant, crypto",
        sources=[SourceType.LOCAL_FOLDER],
        local_inbox=str(ROOT / "samples" / "inbox"),
        audio_library=str(ROOT / "samples" / "audio"),
        output_dir=str(OUTPUT),
        final_duration_seconds=8,
        target_source_clips=10,
        beat_density=2,
    )
    store.save_config(cfg)
    record = TrendCutRunner(store)._run_once_sync()
    if record["status"] != "completed":
        raise SystemExit(record)
    print("TrendScout smoke completed")
    print("Video:", record["delivery"].get("drive_url") or record.get("output_path"))
    print("Sheet:", record["delivery"].get("sheet_url"))


if __name__ == "__main__":
    main()
