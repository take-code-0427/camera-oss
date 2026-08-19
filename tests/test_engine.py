import asyncio
from collections.abc import Sequence

import numpy as np

from flowcam.config import AppConfig, CameraConfig, InferenceConfig, StorageConfig
from flowcam.domain import CrossingEvent, MetricSample, TrackObservation, TrackingResult
from flowcam.engine import FlowEngine


class FakeSource:
    def __init__(self) -> None:
        self._frame = np.zeros((32, 32, 3), dtype=np.uint8)
        self._sent = False

    def read(self):
        if self._sent:
            return None
        self._sent = True
        return self._frame.copy()

    def close(self) -> None:
        return None


class FakeTracker:
    def track(self, frame):
        return TrackingResult(
            observations=[TrackObservation(track_id=1, center=(0.5, 0.5))],
            annotated_frame=frame,
        )


class FakeSink:
    def __init__(self) -> None:
        self.metrics: list[MetricSample] = []
        self.crossings: list[CrossingEvent] = []

    def write_metric(self, metric: MetricSample) -> None:
        self.metrics.append(metric)

    def write_events(self, events: Sequence[CrossingEvent]) -> None:
        self.crossings.extend(events)

    def history(self, since_iso: str) -> list[dict[str, object]]:
        return [metric.as_record() for metric in self.metrics]

    def events(self, since_iso: str) -> list[dict[str, object]]:
        return [event.as_record() for event in self.crossings]

    def close(self) -> None:
        return None


def test_engine_runs_with_protocol_adapters() -> None:
    async def scenario() -> None:
        config = AppConfig(
            camera=CameraConfig(id="test", source="unused", reconnect_seconds=0.01),
            inference=InferenceConfig(sample_fps=100),
            storage=StorageConfig(sqlite_path=":memory:", flush_interval_seconds=0.01),
        )
        sink = FakeSink()
        engine = FlowEngine(config, source=FakeSource(), tracker=FakeTracker(), sink=sink)

        await engine.start()
        await asyncio.sleep(0.05)
        await engine.stop()

        latest = engine.snapshot_metric()
        assert latest.camera_id == "test"
        assert latest.visible_people == 1
        assert sink.metrics

    asyncio.run(scenario())
