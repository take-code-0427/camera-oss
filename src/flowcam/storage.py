from __future__ import annotations

import sqlite3
from pathlib import Path
from threading import Lock


class Storage:
    def __init__(self, path: str):
        db_path = Path(path)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.lock = Lock()
        self._init_schema()

    def _init_schema(self) -> None:
        with self.conn:
            self.conn.execute(
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
            self.conn.execute(
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
            self.conn.execute("CREATE INDEX IF NOT EXISTS idx_metrics_ts ON metrics(timestamp)")
            self.conn.execute("CREATE INDEX IF NOT EXISTS idx_events_ts ON crossing_events(timestamp)")

    def insert_metric(self, metric: dict) -> None:
        with self.lock, self.conn:
            self.conn.execute(
                """
                INSERT INTO metrics(camera_id, timestamp, visible_people, roi_occupancy, flow_in, flow_out)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    metric["camera_id"], metric["timestamp"], metric["visible_people"],
                    metric["roi_occupancy"], metric["flow_in"], metric["flow_out"],
                ),
            )

    def insert_event(self, event: dict) -> None:
        with self.lock, self.conn:
            self.conn.execute(
                """
                INSERT INTO crossing_events(camera_id, line_id, track_id, direction, timestamp)
                VALUES (?, ?, ?, ?, ?)
                """,
                (event["camera_id"], event["line_id"], event["track_id"], event["direction"], event["timestamp"]),
            )

    def history(self, since_iso: str) -> list[dict]:
        with self.lock:
            rows = self.conn.execute(
                "SELECT camera_id,timestamp,visible_people,roi_occupancy,flow_in,flow_out FROM metrics WHERE timestamp >= ? ORDER BY timestamp",
                (since_iso,),
            ).fetchall()
        return [dict(r) for r in rows]

    def events(self, since_iso: str) -> list[dict]:
        with self.lock:
            rows = self.conn.execute(
                "SELECT camera_id,line_id,track_id,direction,timestamp FROM crossing_events WHERE timestamp >= ? ORDER BY timestamp",
                (since_iso,),
            ).fetchall()
        return [dict(r) for r in rows]
