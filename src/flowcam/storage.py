from __future__ import annotations

import sqlite3
from collections.abc import Sequence
from pathlib import Path
from threading import Lock

from .domain import CrossingEvent, MetricSample


class SQLiteMetricsSink:
    def __init__(self, path: str):
        db_path = Path(path)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._lock = Lock()
        self._init_schema()

    def _init_schema(self) -> None:
        with self._conn:
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    camera_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    visible_people INTEGER NOT NULL,
                    roi_occupancy INTEGER NOT NULL,
                    flow_in INTEGER NOT NULL,
                    flow_out INTEGER NOT NULL
                )
                """
            )
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS crossing_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    camera_id TEXT NOT NULL,
                    line_id TEXT NOT NULL,
                    track_id INTEGER NOT NULL,
                    direction TEXT NOT NULL,
                    timestamp TEXT NOT NULL
                )
                """
            )
            self._conn.execute("CREATE INDEX IF NOT EXISTS idx_metrics_ts ON metrics(timestamp)")
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_events_ts ON crossing_events(timestamp)"
            )

    def write_metric(self, metric: MetricSample) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                """
                INSERT INTO metrics(camera_id, timestamp, visible_people, roi_occupancy, flow_in, flow_out)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    metric.camera_id,
                    metric.timestamp,
                    metric.visible_people,
                    metric.roi_occupancy,
                    metric.flow_in,
                    metric.flow_out,
                ),
            )

    def write_events(self, events: Sequence[CrossingEvent]) -> None:
        if not events:
            return
        with self._lock, self._conn:
            self._conn.executemany(
                """
                INSERT INTO crossing_events(camera_id, line_id, track_id, direction, timestamp)
                VALUES (?, ?, ?, ?, ?)
                """,
                [
                    (
                        event.camera_id,
                        event.line_id,
                        event.track_id,
                        event.direction,
                        event.timestamp,
                    )
                    for event in events
                ],
            )

    def history(self, since_iso: str) -> list[dict[str, object]]:
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT camera_id,timestamp,visible_people,roi_occupancy,flow_in,flow_out
                FROM metrics
                WHERE timestamp >= ?
                ORDER BY timestamp
                """,
                (since_iso,),
            ).fetchall()
        return [dict(row) for row in rows]

    def events(self, since_iso: str) -> list[dict[str, object]]:
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT camera_id,line_id,track_id,direction,timestamp
                FROM crossing_events
                WHERE timestamp >= ?
                ORDER BY timestamp
                """,
                (since_iso,),
            ).fetchall()
        return [dict(row) for row in rows]

    def close(self) -> None:
        with self._lock:
            self._conn.close()
