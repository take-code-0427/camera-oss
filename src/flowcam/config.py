from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field, PositiveFloat, PositiveInt

Point = tuple[float, float]


class CameraConfig(BaseModel):
    id: str
    source: str
    reconnect_seconds: PositiveFloat = 2.0


class InferenceConfig(BaseModel):
    model: str = "yolo11n.pt"
    confidence: float = Field(default=0.35, gt=0, le=1)
    imgsz: PositiveInt = 640
    sample_fps: PositiveFloat = 5.0
    device: str | None = None


class RoiConfig(BaseModel):
    id: str = "roi"
    polygon: list[Point] = Field(default_factory=list)


class CrossingLineConfig(BaseModel):
    id: str = "line"
    a: Point
    b: Point


class AnalyticsConfig(BaseModel):
    roi: RoiConfig | None = None
    crossing_line: CrossingLineConfig | None = None
    track_ttl_seconds: PositiveFloat = 5.0


class StorageConfig(BaseModel):
    sqlite_path: str = "./data/flowcam.db"
    flush_interval_seconds: PositiveFloat = 1.0


class ServerConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = Field(default=8000, ge=1, le=65535)


class AppConfig(BaseModel):
    camera: CameraConfig
    inference: InferenceConfig = Field(default_factory=InferenceConfig)
    analytics: AnalyticsConfig = Field(default_factory=AnalyticsConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)
    server: ServerConfig = Field(default_factory=ServerConfig)


def load_config(path: str | Path) -> AppConfig:
    with Path(path).open("r", encoding="utf-8") as file:
        raw = yaml.safe_load(file)
    return AppConfig.model_validate(raw)
