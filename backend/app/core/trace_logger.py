"""Structured JSON trace logging for turn observability."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

_TURN_NUM_RE = re.compile(r"turn_(\d+)\.json$")


class TraceLogger:
    """Writes per-turn JSON trace files for LLM debugging and observability."""

    def __init__(self, base_path: Path) -> None:
        self._base = base_path

    def write_trace(self, session_id: str, turn_index: int, trace: dict) -> Path:
        """Write a trace payload to ``{base}/{session_id}/turn_{turn_index}.json``.

        Returns the path to the written trace file.
        """
        session_dir = self._base / session_id
        session_dir.mkdir(parents=True, exist_ok=True)

        trace["_written_at"] = datetime.now(timezone.utc).isoformat()
        file_path = session_dir / f"turn_{turn_index}.json"
        file_path.write_text(json.dumps(trace, indent=2, default=str), encoding="utf-8")
        return file_path

    def read_latest_trace(self, session_id: str) -> dict | None:
        """Return the highest-numbered trace for a session, or *None*."""
        session_dir = self._base / session_id
        if not session_dir.is_dir():
            return None

        trace_files = list(session_dir.glob("turn_*.json"))
        if not trace_files:
            return None

        def _turn_number(path: Path) -> int:
            m = _TURN_NUM_RE.search(path.name)
            return int(m.group(1)) if m else -1

        latest = max(trace_files, key=_turn_number)
        return json.loads(latest.read_text(encoding="utf-8"))
