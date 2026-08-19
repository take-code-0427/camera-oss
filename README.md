# FlowCam POC

Turn a camera stream into anonymous foot-traffic metrics.

FlowCam is a proof-of-concept for converting existing camera feeds into structured pedestrian-flow data. It intentionally persists **aggregate events and metrics, not video frames**.

## What it does

- MP4 / local video / HLS input through an OpenCV adapter
- Person detection + ByteTrack through an Ultralytics adapter
- ROI occupancy counting
- Bidirectional line-crossing (`in` / `out`) counting
- SQLite time-series storage through a sink adapter
- FastAPI endpoints for latest metrics and history
- Browser dashboard with an annotated MJPEG development preview
- YAML-based camera configuration

## Tooling

The repository uses a modern `uv`-first Python workflow:

- Python 3.12 pinned by `.python-version`
- `pyproject.toml` as the dependency/configuration source of truth
- `uv.lock` committed for reproducible dependency resolution
- `uv` for Python, virtualenv, dependency management, execution and builds
- PEP 735 dependency groups for development tools
- `uv_build` as the build backend
- Ruff for linting and formatting
- ty for static type checking
- pytest for tests
- GitHub Actions using `astral-sh/setup-uv`
- Docker using the official uv binary and frozen lockfile installs

## Quick start

Install uv, then:

```bash
git clone https://github.com/take-code-0427/camera-oss.git
cd camera-oss

uv sync --frozen
cp config.example.yaml config.yaml
uv run flowcam --config config.yaml
```

Open:

- Dashboard: http://127.0.0.1:8000/
- API docs: http://127.0.0.1:8000/docs
- Latest metrics: http://127.0.0.1:8000/api/v1/metrics/latest

The first inference run downloads the configured Ultralytics model weights.

## Development

```bash
uv sync --frozen --all-groups
uv run ruff check .
uv run ruff format .
uv run ty check src tests
uv run pytest
```

Use uv to change dependencies:

```bash
uv add httpx
uv add --dev pytest-cov
uv remove httpx
uv lock
```

Commit both `pyproject.toml` and the regenerated `uv.lock` after dependency changes. CI and Docker use `--frozen`, so they fail rather than silently changing the resolved dependency graph.

## Architecture

The core is deliberately adapter-based rather than coupling OpenCV, YOLO and SQLite into one engine.

```text
                    +-------------------+
Video / HLS ------> | FrameSource       |
                    | OpenCV adapter    |
                    +---------+---------+
                              |
                              v
                    +-------------------+
                    | PersonTracker     |
                    | Ultralytics       |
                    | YOLO + ByteTrack  |
                    +---------+---------+
                              |
                              v
                    +-------------------+
                    | FlowAnalytics     |
                    | pure domain logic |
                    +---------+---------+
                              |
                  MetricSample / CrossingEvent
                              |
                              v
                    +-------------------+
                    | MetricsSink       |
                    | SQLite adapter    |
                    +-------------------+
```

`FrameSource`, `PersonTracker` and `MetricsSink` are Python `Protocol`s. The orchestration layer depends on those interfaces, not concrete libraries.

This makes the next adapters straightforward:

- JPEG snapshot source
- RTSP-specific source
- prerecorded/test source
- ONNX / TensorRT tracker
- PostgreSQL / TimescaleDB / ClickHouse sink
- Kafka / NATS event sink

The runtime itself is async. OpenCV, inference and SQLite remain blocking libraries, so the engine executes those boundaries with `asyncio.to_thread()` while FastAPI and lifecycle management remain on the event loop.

## Project layout

```text
src/flowcam/
  api.py         FastAPI transport / lifespan wiring
  analytics.py   ROI + line-crossing domain logic
  cli.py         CLI entry point
  config.py      Pydantic configuration models
  domain.py      typed domain records
  engine.py      async orchestration pipeline
  ports.py       Protocol interfaces
  sources.py     camera/video input adapters
  storage.py     persistence adapters
  tracking.py    detector/tracker adapters
```

## Try with a video

Edit `config.yaml`:

```yaml
camera:
  id: demo
  source: ./sample.mp4
```

For HLS:

```yaml
camera:
  id: public-camera
  source: https://example.com/live/index.m3u8
```

OpenCV/FFmpeg must be able to decode the stream.

## Configuration

Coordinates are normalized to `[0, 1]`, so configs are independent of stream resolution.

```yaml
camera:
  id: demo
  source: ./sample.mp4
  reconnect_seconds: 2

inference:
  model: yolo11n.pt
  confidence: 0.35
  imgsz: 640
  sample_fps: 5
  device: null

analytics:
  roi:
    id: sidewalk
    polygon:
      - [0.05, 0.10]
      - [0.95, 0.10]
      - [0.95, 0.95]
      - [0.05, 0.95]
  crossing_line:
    id: entrance
    a: [0.50, 0.20]
    b: [0.50, 0.90]
  track_ttl_seconds: 5

storage:
  sqlite_path: ./data/flowcam.db
  flush_interval_seconds: 1

server:
  host: 0.0.0.0
  port: 8000
```

`in` and `out` are defined by the sign change relative to the directed line from `a` to `b`. Swap `a` and `b` if the direction is reversed for a camera.

## API

- `GET /healthz`
- `GET /api/v1/metrics/latest`
- `GET /api/v1/metrics/history?minutes=60`
- `GET /api/v1/events?minutes=60`
- `GET /api/v1/preview.mjpg`

The preview endpoint exists for POC/debugging. A production edge deployment should normally expose only aggregate data.

## Privacy model

The intended production architecture is edge-first aggregation:

1. Decode frames locally.
2. Detect and track only long enough to compute aggregate metrics.
3. Use ephemeral tracker IDs; do not create persistent person identities.
4. Do not perform face recognition.
5. Persist counts/events rather than raw frames.
6. Disable the preview endpoint when raw video must not leave the edge device.

A public livestream being technically accessible does not automatically grant rights to reuse, republish or commercially analyze it. Verify the stream operator's license/terms and applicable privacy rules before using a real feed.

## Docker

```bash
docker compose up --build
```

The image copies `pyproject.toml` and `uv.lock`, then installs with `uv sync --frozen`; it does not resolve dependencies during the build or install the application with pip.

## Next steps

- JPEG snapshot adapter
- native RTSP reconnect/backoff tuning
- multiple cameras per process
- per-zone pass-by and entrance conversion rate
- homography/world-coordinate calibration
- Prometheus / TimescaleDB / ClickHouse sinks
- offline annotation + accuracy evaluation CLI
- camera registry (`registry://...`) with reusable configs

## License

Apache-2.0. See `LICENSE`.
