from __future__ import annotations

import json
from pathlib import Path

from .config import AutomationConfig
from .sources import CandidateClip


class DedupeStore:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            self.data = json.loads(path.read_text())
        else:
            self.data = {"source_urls": [], "fingerprints": []}

    def seen(self, clip: CandidateClip, config: AutomationConfig) -> bool:
        mode = config.dedupe_mode.value if hasattr(config.dedupe_mode, "value") else config.dedupe_mode
        by_url = clip.source_url in self.data.get("source_urls", [])
        by_fp = clip.fingerprint in self.data.get("fingerprints", [])
        if mode == "source_url":
            return by_url
        if mode == "similar_audio":
            return by_fp
        return by_url or by_fp

    def add(self, clip: CandidateClip) -> None:
        self.data.setdefault("source_urls", [])
        self.data.setdefault("fingerprints", [])
        if clip.source_url not in self.data["source_urls"]:
            self.data["source_urls"].append(clip.source_url)
        if clip.fingerprint not in self.data["fingerprints"]:
            self.data["fingerprints"].append(clip.fingerprint)

    def save(self) -> None:
        self.path.write_text(json.dumps(self.data, indent=2))
