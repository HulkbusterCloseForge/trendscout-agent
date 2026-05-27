from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .beatmatch import BeatMatchPlan, SourceClip, build_beatmatched_video, synth_demo_audio
from .config import AutomationConfig
from .dedupe import DedupeStore
from .google_outputs import deliver_outputs
from .llm import build_search_plan, verify_candidate
from .sources import discover_candidates
from .store import JsonStore


class TrendCutRunner:
    def __init__(self, store: JsonStore):
        self.store = store
        self.running = False
        self.scheduler_task: asyncio.Task | None = None
        self.current_run: dict | None = None
        self.next_run_at: str | None = None

    def status(self) -> dict:
        return {
            "running": self.running,
            "current_run": self.current_run,
            "next_run_at": self.next_run_at,
            "history": self.store.load_history()[:25],
        }

    async def start(self) -> None:
        self.running = True
        if not self.scheduler_task or self.scheduler_task.done():
            self.scheduler_task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        self.running = False
        if self.scheduler_task:
            self.scheduler_task.cancel()
            try:
                await self.scheduler_task
            except asyncio.CancelledError:
                pass

    async def _loop(self) -> None:
        while self.running:
            await self.run_once()
            cfg = self.store.load_config()
            next_run = datetime.now(timezone.utc) + timedelta(minutes=max(1, cfg.interval_minutes))
            self.next_run_at = next_run.isoformat()
            await asyncio.sleep(max(1, cfg.interval_minutes) * 60)

    async def run_once(self) -> dict:
        return await asyncio.to_thread(self._run_once_sync)

    def _select_audio(self, cfg: AutomationConfig) -> Path:
        if cfg.audio_path and Path(cfg.audio_path).exists():
            return Path(cfg.audio_path)
        audio_dir = Path(cfg.audio_library)
        audio_dir.mkdir(parents=True, exist_ok=True)
        for path in sorted(audio_dir.glob("*")):
            if path.suffix.lower() in {".mp3", ".wav", ".m4a", ".aac"}:
                return path
        return synth_demo_audio(audio_dir / "trendscout_demo_120bpm.wav", duration=max(60, cfg.final_duration_seconds + 5))

    def _run_once_sync(self) -> dict:
        cfg = self.store.load_config()
        cfg.ensure_dirs()
        run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "_" + uuid.uuid4().hex[:8]
        output_root = Path(cfg.output_dir)
        run_dir = output_root / "runs" / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        self.current_run = {"run_id": run_id, "status": "planning", "started_at": datetime.now(timezone.utc).isoformat()}

        warnings: list[str] = []
        accepted: list[dict] = []
        rejected: list[dict] = []
        plan = build_search_plan(cfg)
        self.current_run.update({"status": "discovering", "search_plan": plan.__dict__})
        try:
            candidates = discover_candidates(cfg, plan, run_dir)
        except Exception as exc:
            record = {
                "run_id": run_id,
                "status": "failed",
                "error": str(exc),
                "config": cfg.to_dict(),
                "search_plan": plan.__dict__,
                "accepted": accepted,
                "rejected": rejected,
                "warnings": warnings,
                "finished_at": datetime.now(timezone.utc).isoformat(),
            }
            self.store.append_history(record)
            manifest_path = run_dir / "manifest.json"
            manifest_path.write_text(__import__("json").dumps(record, indent=2, default=str))
            self.current_run = None
            return record
        dedupe = DedupeStore(output_root / "dedupe.json")

        self.current_run.update({"status": "filtering", "candidate_count": len(candidates)})
        clips: list[SourceClip] = []
        seen_authors: set[str] = set()
        for candidate in candidates:
            if dedupe.seen(candidate, cfg):
                rejected.append({"source_url": candidate.source_url, "reason": "duplicate", "metadata": candidate.metadata})
                continue
            decision = verify_candidate(cfg, plan, candidate.metadata, len(accepted))
            item = {"source_url": candidate.source_url, "path": str(candidate.path), "decision": decision.__dict__, "metadata": candidate.metadata}
            if decision.accepted:
                author = str(candidate.metadata.get("author") or candidate.metadata.get("title") or "").strip().lower()
                if author and author in seen_authors:
                    rejected.append({**item, "reason": "duplicate author/source account for demo diversity"})
                    continue
                accepted.append(item)
                if author:
                    seen_authors.add(author)
                clips.append(SourceClip(candidate.path, candidate.source_url, decision.rationale))
                dedupe.add(candidate)
                if len(clips) >= cfg.target_source_clips:
                    break
            else:
                rejected.append(item)

        if not clips:
            record = {
                "run_id": run_id,
                "status": "failed",
                "error": "No clips matched the interest prompt",
                "config": cfg.to_dict(),
                "search_plan": plan.__dict__,
                "accepted": accepted,
                "rejected": rejected,
                "warnings": warnings,
                "finished_at": datetime.now(timezone.utc).isoformat(),
            }
            self.store.append_history(record)
            manifest_path = run_dir / "manifest.json"
            manifest_path.write_text(__import__("json").dumps(record, indent=2, default=str))
            self.current_run = None
            return record

        self.current_run.update({"status": "rendering", "accepted_count": len(accepted)})
        audio_path = self._select_audio(cfg)
        video_path = run_dir / f"{run_id}_trendscout.mp4"
        render_plan = BeatMatchPlan(
            audio_path=audio_path,
            beat_density=cfg.beat_density,
            orientation=cfg.orientation.value if hasattr(cfg.orientation, "value") else cfg.orientation,
            final_duration_seconds=cfg.final_duration_seconds,
            clips=clips,
        )
        try:
            build_beatmatched_video(render_plan, video_path)
            status = "completed"
            error = ""
        except Exception as exc:
            status = "failed"
            error = str(exc)
            warnings.append(error)

        delivery = {}
        if status == "completed":
            self.current_run.update({"status": "delivering"})
            delivery = deliver_outputs(video_path, {
                "run_id": run_id,
                "config": cfg.to_dict(),
                "accepted": accepted,
                "rejected": rejected,
                "warnings": warnings,
            }, output_root)
            dedupe.save()

        record = {
            "run_id": run_id,
            "status": status,
            "error": error,
            "config": cfg.to_dict(),
            "search_plan": plan.__dict__,
            "accepted": accepted,
            "rejected": rejected,
            "output_path": str(video_path) if status == "completed" else "",
            "delivery": delivery,
            "warnings": warnings,
            "finished_at": datetime.now(timezone.utc).isoformat(),
        }
        manifest_path = run_dir / "manifest.json"
        manifest_path.write_text(__import__("json").dumps(record, indent=2, default=str))
        self.store.append_history(record)
        self.current_run = None
        return record
