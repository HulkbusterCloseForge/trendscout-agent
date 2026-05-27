from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

from .config import AutomationConfig


def _json_default(value: Any):
    if hasattr(value, "value"):
        return value.value
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, Path):
        return str(value)
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


class JsonStore:
    def __init__(self, root: Path):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self.config_path = self.root / "config.json"
        self.history_path = self.root / "history.json"

    def load_config(self) -> AutomationConfig:
        if self.config_path.exists():
            return AutomationConfig.from_dict(json.loads(self.config_path.read_text()))
        cfg = AutomationConfig()
        self.save_config(cfg)
        return cfg

    def save_config(self, config: AutomationConfig) -> None:
        config.ensure_dirs()
        self.config_path.write_text(json.dumps(config.to_dict(), indent=2, default=_json_default))

    def load_history(self) -> list[dict]:
        if not self.history_path.exists():
            return []
        return json.loads(self.history_path.read_text())

    def append_history(self, record: dict) -> None:
        history = self.load_history()
        history.insert(0, record)
        self.history_path.write_text(json.dumps(history[:200], indent=2, default=_json_default))
