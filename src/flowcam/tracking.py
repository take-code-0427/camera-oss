from __future__ import annotations

from typing import Any

from ultralytics import YOLO

from .config import InferenceConfig
from .domain import Frame, TrackObservation, TrackingResult


class UltralyticsPersonTracker:
    def __init__(self, config: InferenceConfig):
        self._config = config
        self._model = YOLO(config.model)

    def track(self, frame: Frame) -> TrackingResult:
        kwargs: dict[str, Any] = {
            "source": frame,
            "persist": True,
            "classes": [0],
            "conf": self._config.confidence,
            "imgsz": self._config.imgsz,
            "tracker": "bytetrack.yaml",
            "verbose": False,
        }
        if self._config.device:
            kwargs["device"] = self._config.device

        result = self._model.track(**kwargs)[0]
        observations: list[TrackObservation] = []

        if result.boxes is not None and result.boxes.id is not None:
            xyxy = result.boxes.xyxy.cpu().tolist()
            ids = result.boxes.id.int().cpu().tolist()
            height, width = frame.shape[:2]
            for box, track_id in zip(xyxy, ids, strict=True):
                x1, y1, x2, y2 = box
                center = (((x1 + x2) / 2) / width, ((y1 + y2) / 2) / height)
                observations.append(TrackObservation(track_id=track_id, center=center))

        return TrackingResult(observations=observations, annotated_frame=result.plot())
