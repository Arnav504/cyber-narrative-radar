"""In-process ingest run status for the dashboard / operators."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from threading import Lock
from typing import Any


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat().replace("+00:00", "Z")


@dataclass
class IngestRunSnapshot:
    """Latest scheduled / manual ingest outcome."""

    enabled: bool = False
    interval_seconds: int = 180
    running: bool = False
    runs_completed: int = 0
    last_started_at: datetime | None = None
    last_finished_at: datetime | None = None
    last_success_at: datetime | None = None
    next_run_at: datetime | None = None
    last_error: str | None = None
    last_stats: dict[str, Any] = field(default_factory=dict)
    last_score_stats: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["last_started_at"] = _iso(self.last_started_at)
        payload["last_finished_at"] = _iso(self.last_finished_at)
        payload["last_success_at"] = _iso(self.last_success_at)
        payload["next_run_at"] = _iso(self.next_run_at)
        return payload


class IngestStatusTracker:
    """Thread-safe status mirror for the optional live RSS scheduler."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._snapshot = IngestRunSnapshot()

    def configure(self, *, enabled: bool, interval_seconds: int) -> None:
        with self._lock:
            self._snapshot.enabled = enabled
            self._snapshot.interval_seconds = interval_seconds

    def mark_next_run(self, when: datetime | None) -> None:
        with self._lock:
            self._snapshot.next_run_at = when

    def begin_run(self) -> None:
        with self._lock:
            self._snapshot.running = True
            self._snapshot.last_started_at = _utc_now()
            self._snapshot.last_error = None

    def finish_run(
        self,
        *,
        ok: bool,
        stats: dict[str, Any] | None = None,
        score_stats: dict[str, Any] | None = None,
        error: str | None = None,
        next_run_at: datetime | None = None,
    ) -> None:
        with self._lock:
            now = _utc_now()
            self._snapshot.running = False
            self._snapshot.last_finished_at = now
            self._snapshot.runs_completed += 1
            if stats is not None:
                self._snapshot.last_stats = dict(stats)
            if score_stats is not None:
                self._snapshot.last_score_stats = dict(score_stats)
            if ok:
                self._snapshot.last_success_at = now
                self._snapshot.last_error = None
            else:
                self._snapshot.last_error = error or "unknown error"
            if next_run_at is not None:
                self._snapshot.next_run_at = next_run_at

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return self._snapshot.to_dict()


ingest_status = IngestStatusTracker()
