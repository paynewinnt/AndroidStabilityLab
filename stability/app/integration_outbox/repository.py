from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping, Sequence


class RepositoryMixin:
    def _load_event_registry(self) -> list[dict[str, Any]]:
        payload = self._load_registry(self._events_path)
        return [dict(item) for item in payload if isinstance(item, Mapping)]

    def _load_webhook_registry(self) -> list[dict[str, Any]]:
        payload = self._load_registry(self._webhooks_path)
        return [dict(item) for item in payload if isinstance(item, Mapping)]

    @staticmethod
    def _load_registry(path: Path) -> list[Any]:
        if not path.exists():
            return []
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return []
        return list(payload) if isinstance(payload, list) else []

    def _save_registry(self, path: Path, payload: Sequence[Mapping[str, Any]]) -> None:
        self._root_dir.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(list(payload), ensure_ascii=False, indent=2), encoding="utf-8")
