from __future__ import annotations

import asyncio
import contextlib
import time
from datetime import UTC, datetime

import cv2
import numpy as np

from .analytics import FlowAnalytics
from .config import AppConfig
from .domain import Frame, MetricSample
from .ports import FrameSource, MetricsSink, PersonTracker


class FlowEngine:
    def __init__(
        self,
        config: AppConfig,
        source: FrameSource,
        tracker: PersonTracker,
        sink: MetricsSink,
    ):
        self.config = config
        self.source = source
        self.tracker = tracker
        self.sink = sink
        self.analytics = FlowAnalytics(config.camera.id, config.analytics)
        self._latest_metric = MetricSample(
            camera_id=config.camera.id,
            timestamp=datetime.now(UTC).isoformat(),
            visible_people=0,
            roi_occupancy=0,
            flow_in=0,
            flow_out=0,
        )
        self._latest_jpeg: bytes | None = None
        self._task: asyncio.Task[None] | None = None
        self._stopping = asyncio.Event()

    async def start(self) -> None:
        if self._task and not self._task.done():
            return
        self._stopping.clear()
        self._task = asyncio.create_task(self._run(), name="flowcam-engine")

    async def stop(self) -> None:
        self._stopping.set()
        if self._task is not None:
            await self._task
        await asyncio.to_thread(self.source.close)
        await asyncio.to_thread(self.sink.close)

    async def _run(self) -> None:
        min_interval = 1.0 / max(self.config.inference.sample_fps, 0.1)
        last_processed = 0.0
        last_flushed = 0.0

        while not self._stopping.is_set():
            frame = await asyncio.to_thread(self.source.read)
            if frame is None:
                with contextlib.suppress(TimeoutError):
                    await asyncio.wait_for(
                        self._stopping.wait(),
                        timeout=self.config.camera.reconnect_seconds,
                    )
                continue

            now = time.monotonic()
            sleep_for = min_interval - (now - last_processed)
            if sleep_for > 0:
                try:
                    await asyncio.wait_for(self._stopping.wait(), timeout=sleep_for)
                    continue
                except TimeoutError:
                    pass
            last_processed = time.monotonic()

            tracking = await asyncio.to_thread(self.tracker.track, frame)
            roi_occupancy, events = self.analytics.update(tracking.observations, last_processed)
            metric = MetricSample(
                camera_id=self.config.camera.id,
                timestamp=datetime.now(UTC).isoformat(),
                visible_people=len(tracking.observations),
                roi_occupancy=roi_occupancy,
                flow_in=self.analytics.flow_in,
                flow_out=self.analytics.flow_out,
            )

            annotated = tracking.annotated_frame
            self._draw_geometry(annotated)
            self._latest_metric = metric
            self._latest_jpeg = await asyncio.to_thread(self._encode_jpeg, annotated)

            if events:
                await asyncio.to_thread(self.sink.write_events, events)

            if last_processed - last_flushed >= self.config.storage.flush_interval_seconds:
                await asyncio.to_thread(self.sink.write_metric, metric)
                last_flushed = last_processed

    @staticmethod
    def _encode_jpeg(frame: Frame) -> bytes | None:
        ok, encoded = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
        return encoded.tobytes() if ok else None

    def _draw_geometry(self, frame: Frame) -> None:
        height, width = frame.shape[:2]
        roi = self.config.analytics.roi
        if roi and len(roi.polygon) >= 3:
            points = np.array(
                [[int(x * width), int(y * height)] for x, y in roi.polygon],
                dtype=np.int32,
            )
            cv2.polylines(frame, [points], True, (255, 255, 255), 2)

        line = self.config.analytics.crossing_line
        if line:
            a = (int(line.a[0] * width), int(line.a[1] * height))
            b = (int(line.b[0] * width), int(line.b[1] * height))
            cv2.line(frame, a, b, (255, 255, 255), 2)

    def snapshot_metric(self) -> MetricSample:
        return self._latest_metric

    def snapshot_jpeg(self) -> bytes | None:
        return self._latest_jpeg
