from __future__ import annotations

from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel, Field


class CameraConfig(BaseModel):
    id: str
    source: str
    reconnect_seconds: float = 2.0


class InferenceConfig(BaseModel):
    model: str = "yolo11n.pt"
    confidence: float = 0.35
    imgsz: int = 640
    sample_fps: float = 5.0
    device: Optional[str] = None


class RoiConfig(BaseModel):
    id: str = "roi"
    polygon: list[tuple[float, float]] = Field(default_factory=list)


class CrossingLineConfig(BaseModel):
    id: str = "line"
    a: tuple[float, float]
    b: tuple[float, float]


class AnalyticsConfig(BaseModel):
    roi: Optional[RoiConfig] = None
    crossing_line: Optional[CrossingLineConfig] = None
    track_ttl_seconds: float = 5.0


class StorageConfig(BaseModel):
    sqlite_path: str = "./data/flowcam.db"
    flush_interval_seconds: float = 1.0


class ServerConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8000


class AppConfig(BaseModel):
    camera: CameraConfig
    inference: InferenceConfig = Field(default_factory=InferenceConfig)
    analytics: AnalyticsConfig = Field(default_factory=AnalyticsConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)
    server: ServerConfig = Field(default_factory=ServerConfig)


def load_config(path: str | Path) -> AppConfig:
    with Path(path).open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    return AppConfig.model_validate(raw)
