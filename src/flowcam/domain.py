from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal

import numpy as np
from numpy.typing import NDArray

Point = tuple[float, float]
Frame = NDArray[np.uint8]
Direction = Literal["in", "out"]


@dataclass(slots=True, frozen=True)
class TrackObservation:
    track_id: int
    center: Point


@dataclass(slots=True, frozen=True)
class CrossingEvent:
    camera_id: str
    line_id: str
    track_id: int
    direction: Direction
    timestamp: str

    def as_record(self) -> dict[str, object]:
        return asdict(self)


@dataclass(slots=True, frozen=True)
class MetricSample:
    camera_id: str
    timestamp: str
    visible_people: int
    roi_occupancy: int
    flow_in: int
    flow_out: int

    def as_record(self) -> dict[str, object]:
        return asdict(self)


@dataclass(slots=True)
class TrackingResult:
    observations: list[TrackObservation]
    annotated_frame: Frame
