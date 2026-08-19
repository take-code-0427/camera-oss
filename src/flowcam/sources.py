from __future__ import annotations

import cv2
import numpy as np

from .domain import Frame


class OpenCVFrameSource:
    def __init__(self, source: str):
        self._source = source
        self._capture: cv2.VideoCapture | None = None

    def _ensure_open(self) -> bool:
        if self._capture is not None and self._capture.isOpened():
            return True
        self.close()
        capture = cv2.VideoCapture(self._source)
        if not capture.isOpened():
            capture.release()
            return False
        self._capture = capture
        return True

    def read(self) -> Frame | None:
        if not self._ensure_open():
            return None
        assert self._capture is not None
        ok, frame = self._capture.read()
        if not ok:
            self.close()
            return None
        return np.asarray(frame, dtype=np.uint8)

    def close(self) -> None:
        if self._capture is not None:
            self._capture.release()
            self._capture = None
