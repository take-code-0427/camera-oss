from __future__ import annotations

from datetime import UTC, datetime

import cv2
import numpy as np

from .config import AnalyticsConfig
from .domain import CrossingEvent, Point, TrackObservation


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

    def update(
        self,
        observations: list[TrackObservation],
        now_monotonic: float,
    ) -> tuple[int, list[CrossingEvent]]:
        events: list[CrossingEvent] = []
        roi_occupancy = 0

        for observation in observations:
            self._last_seen[observation.track_id] = now_monotonic

            if self.config.roi and self._inside_polygon(
                observation.center,
                self.config.roi.polygon,
            ):
                roi_occupancy += 1

            line = self.config.crossing_line
            if line is None:
                continue

            side = self._side(observation.center, line.a, line.b)
            previous = self._last_side.get(observation.track_id)
            self._last_side[observation.track_id] = side

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
                    track_id=observation.track_id,
                    direction=direction,
                    timestamp=datetime.now(UTC).isoformat(),
                )
            )

        ttl = self.config.track_ttl_seconds
        stale = [
            track_id
            for track_id, seen_at in self._last_seen.items()
            if now_monotonic - seen_at > ttl
        ]
        for track_id in stale:
            self._last_seen.pop(track_id, None)
            self._last_side.pop(track_id, None)

        return roi_occupancy, events
