from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from .domain import CrossingEvent, Frame, MetricSample, TrackingResult


class FrameSource(Protocol):
    def read(self) -> Frame | None: ...

    def close(self) -> None: ...


class PersonTracker(Protocol):
    def track(self, frame: Frame) -> TrackingResult: ...


class MetricsSink(Protocol):
    def write_metric(self, metric: MetricSample) -> None: ...

    def write_events(self, events: Sequence[CrossingEvent]) -> None: ...

    def history(self, since_iso: str) -> list[dict[str, object]]: ...

    def events(self, since_iso: str) -> list[dict[str, object]]: ...

    def close(self) -> None: ...
