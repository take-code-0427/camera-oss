from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

import cv2
import numpy as np

from .config import AnalyticsConfig

Point = tuple[float, float]


@dataclass(slots=True)
class TrackObservation:
    track_id: int
    center: Point


@dataclass(slots=True)
class CrossingEvent:
    camera_id: str
    line_id: str
    track_id: int
    direction: str
    timestamp: str


class FlowAnalytics:
    def __init__(self, camera_id: str, config: AnalyticsConfig):
        self.camera_id = camera_id
        self.config = config
        self._last_side: dict[int, float] = {}
        self._last_seen: dict[int, float] = {}
        self.flow_in = 0
        self.flow_out = 0

    @staticmethod
    def _side(point: Point, a: Point, b: Point) -> float:
        return (b[0] - a[0]) * (point[1] - a[1]) - (b[1] - a[1]) * (point[0] - a[0])

    @staticmethod
    def _inside_polygon(point: Point, polygon: list[Point]) -> bool:
        if len(polygon) < 3:
            return False
        contour = np.array(polygon, dtype=np.float32)
        return cv2.pointPolygonTest(contour, point, False) >= 0

    def update(self, observations: list[TrackObservation], now_monotonic: float) -> tuple[int, list[CrossingEvent]]:
        events: list[CrossingEvent] = []
        roi_occupancy = 0

        for obs in observations:
            self._last_seen[obs.track_id] = now_monotonic

            if self.config.roi and self._inside_polygon(obs.center, self.config.roi.polygon):
                roi_occupancy += 1

            line = self.config.crossing_line
            if not line:
                continue

            side = self._side(obs.center, line.a, line.b)
            previous = self._last_side.get(obs.track_id)
            self._last_side[obs.track_id] = side

            if previous is None or previous == 0 or side == 0 or previous * side >= 0:
                continue

            direction = "in" if previous < 0 < side else "out"
            if direction == "in":
                self.flow_in += 1
            else:
                self.flow_out += 1

            events.append(
                CrossingEvent(
                    camera_id=self.camera_id,
                    line_id=line.id,
                    track_id=obs.track_id,
                    direction=direction,
                    timestamp=datetime.now(timezone.utc).isoformat(),
                )
            )

        ttl = self.config.track_ttl_seconds
        stale = [tid for tid, seen in self._last_seen.items() if now_monotonic - seen > ttl]
        for tid in stale:
            self._last_seen.pop(tid, None)
            self._last_side.pop(tid, None)

        return roi_occupancy, events
