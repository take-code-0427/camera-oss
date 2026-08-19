from __future__ import annotations

import threading
import time
from dataclasses import asdict
from datetime import datetime, timezone

import cv2
from ultralytics import YOLO

from .analytics import FlowAnalytics, TrackObservation
from .config import AppConfig
from .storage import Storage


class FlowEngine:
    def __init__(self, config: AppConfig, storage: Storage):
        self.config = config
        self.storage = storage
        self.analytics = FlowAnalytics(config.camera.id, config.analytics)
        self.model = YOLO(config.inference.model)
        self.latest_metric: dict = {
            "camera_id": config.camera.id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "visible_people": 0,
            "roi_occupancy": 0,
            "flow_in": 0,
            "flow_out": 0,
        }
        self.latest_jpeg: bytes | None = None
        self.lock = threading.Lock()
        self.stop_event = threading.Event()
        self.thread: threading.Thread | None = None

    def start(self) -> None:
        if self.thread and self.thread.is_alive():
            return
        self.thread = threading.Thread(target=self._run, daemon=True, name="flowcam-engine")
        self.thread.start()

    def stop(self) -> None:
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=3)

    def _open_capture(self):
        cap = cv2.VideoCapture(self.config.camera.source)
        if not cap.isOpened():
            cap.release()
            return None
        return cap

    def _run(self) -> None:
        cap = None
        last_processed = 0.0
        last_flushed = 0.0
        min_interval = 1.0 / max(self.config.inference.sample_fps, 0.1)

        while not self.stop_event.is_set():
            if cap is None:
                cap = self._open_capture()
                if cap is None:
                    time.sleep(self.config.camera.reconnect_seconds)
                    continue

            ok, frame = cap.read()
            if not ok:
                cap.release()
                cap = None
                time.sleep(self.config.camera.reconnect_seconds)
                continue

            now = time.monotonic()
            if now - last_processed < min_interval:
                continue
            last_processed = now

            kwargs = {
                "source": frame,
                "persist": True,
                "classes": [0],
                "conf": self.config.inference.confidence,
                "imgsz": self.config.inference.imgsz,
                "tracker": "bytetrack.yaml",
                "verbose": False,
            }
            if self.config.inference.device:
                kwargs["device"] = self.config.inference.device

            result = self.model.track(**kwargs)[0]
            observations: list[TrackObservation] = []

            if result.boxes is not None and result.boxes.id is not None:
                xyxy = result.boxes.xyxy.cpu().tolist()
                ids = result.boxes.id.int().cpu().tolist()
                height, width = frame.shape[:2]
                for box, track_id in zip(xyxy, ids):
                    x1, y1, x2, y2 = box
                    center = (((x1 + x2) / 2) / width, ((y1 + y2) / 2) / height)
                    observations.append(TrackObservation(track_id=track_id, center=center))

            roi_occupancy, events = self.analytics.update(observations, now)
            metric = {
                "camera_id": self.config.camera.id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "visible_people": len(observations),
                "roi_occupancy": roi_occupancy,
                "flow_in": self.analytics.flow_in,
                "flow_out": self.analytics.flow_out,
            }

            annotated = result.plot()
            self._draw_geometry(annotated)
            ok_jpeg, encoded = cv2.imencode(".jpg", annotated, [int(cv2.IMWRITE_JPEG_QUALITY), 80])

            with self.lock:
                self.latest_metric = metric
                if ok_jpeg:
                    self.latest_jpeg = encoded.tobytes()

            for event in events:
                self.storage.insert_event(asdict(event))

            if now - last_flushed >= self.config.storage.flush_interval_seconds:
                self.storage.insert_metric(metric)
                last_flushed = now

        if cap is not None:
            cap.release()

    def _draw_geometry(self, frame) -> None:
        h, w = frame.shape[:2]
        roi = self.config.analytics.roi
        if roi and len(roi.polygon) >= 3:
            pts = [[int(x * w), int(y * h)] for x, y in roi.polygon]
            cv2.polylines(frame, [__import__("numpy").array(pts, dtype="int32")], True, (255, 255, 255), 2)

        line = self.config.analytics.crossing_line
        if line:
            a = (int(line.a[0] * w), int(line.a[1] * h))
            b = (int(line.b[0] * w), int(line.b[1] * h))
            cv2.line(frame, a, b, (255, 255, 255), 2)

    def snapshot_metric(self) -> dict:
        with self.lock:
            return dict(self.latest_metric)

    def snapshot_jpeg(self) -> bytes | None:
        with self.lock:
            return self.latest_jpeg
