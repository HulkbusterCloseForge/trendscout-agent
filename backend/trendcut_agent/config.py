from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Literal


class Orientation(str, Enum):
    VERTICAL = "vertical"
    HORIZONTAL = "horizontal"


class Strictness(str, Enum):
    EXACT = "exact"
    BALANCED = "balanced"
    EXPLORE_ADJACENT = "explore_adjacent"


class SourceType(str, Enum):
    LOCAL_FOLDER = "local_folder"
    APIFY_TIKTOK = "apify_tiktok"
    YOUTUBE = "youtube"


class MusicSource(str, Enum):
    ROYALTY_FREE = "royalty_free"
    USER_UPLOAD = "user_upload"
    TREND_METADATA = "trend_metadata"


class DedupeMode(str, Enum):
    SOURCE_URL = "source_url"
    SIMILAR_AUDIO = "similar_audio"
    BOTH = "both"


@dataclass
class AutomationConfig:
    run_name: str = "TrendScout Demo"
    interest_prompt: str = "AI tools and automation"
    exclusions: str = ""
    sources: list[SourceType] = field(default_factory=lambda: [SourceType.LOCAL_FOLDER])
    orientation: Orientation = Orientation.HORIZONTAL
    interval_minutes: int = 60
    final_duration_seconds: int = 30
    target_source_clips: int = 8
    beat_density: Literal[1, 2, 4, 8] = 2
    music_source: MusicSource = MusicSource.ROYALTY_FREE
    audio_path: str = ""
    region: str = "global"
    strictness: Strictness = Strictness.BALANCED
    auto_widen_search: bool = True
    max_source_age_days: int = 7
    dedupe_mode: DedupeMode = DedupeMode.BOTH
    processing_mode: Literal["cloud", "local", "auto"] = "cloud"
    google_drive_folder_id: str = ""
    google_sheet_id: str = ""
    local_inbox: str = "./samples/inbox"
    audio_library: str = "./samples/audio"
    apify_actor_id: str = "clockworks/tiktok-scraper"
    apify_results_limit: int = 40
    min_source_duration_seconds: float = 1.0
    max_source_duration_seconds: float = 90.0
    output_dir: str = "./output"

    @classmethod
    def from_dict(cls, data: dict) -> "AutomationConfig":
        clean = dict(data or {})
        if "sources" in clean:
            clean["sources"] = [SourceType(s) for s in clean.get("sources") or [SourceType.LOCAL_FOLDER]]
        if "orientation" in clean:
            clean["orientation"] = Orientation(clean["orientation"])
        if "strictness" in clean:
            clean["strictness"] = Strictness(clean["strictness"])
        if "music_source" in clean:
            clean["music_source"] = MusicSource(clean["music_source"])
        if "dedupe_mode" in clean:
            clean["dedupe_mode"] = DedupeMode(clean["dedupe_mode"])
        clean["beat_density"] = int(clean.get("beat_density", 2))
        if clean["beat_density"] not in (1, 2, 4, 8):
            raise ValueError("beat_density must be one of 1, 2, 4, 8")
        return cls(**clean)

    def to_dict(self) -> dict:
        data = asdict(self)
        data["sources"] = [str(s.value if hasattr(s, "value") else s) for s in self.sources]
        for key in ("orientation", "strictness", "music_source", "dedupe_mode"):
            value = data[key]
            data[key] = value.value if hasattr(value, "value") else value
        return data

    def ensure_dirs(self) -> None:
        for path in [self.local_inbox, self.audio_library, self.output_dir]:
            Path(path).mkdir(parents=True, exist_ok=True)
