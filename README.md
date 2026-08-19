# FlowCam POC

Turn a camera stream into anonymous foot-traffic metrics.

This repository is a first proof-of-concept for converting existing camera feeds into structured pedestrian-flow data. It intentionally stores **aggregate events and metrics, not video frames**.

## What it does

- MP4 / local video / HLS input via OpenCV
- Person detection + tracking with Ultralytics YOLO and ByteTrack
- ROI occupancy counting
- Bidirectional line-crossing (`in` / `out`) counting
- SQLite time-series storage
- FastAPI endpoints for latest metrics and history
- Browser dashboard with a live annotated MJPEG preview
- YAML-based camera configuration

## Quick start

Python 3.11+ is recommended.

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -e .
cp config.example.yaml config.yaml
flowcam run --config config.yaml
```

Open:

- Dashboard: http://127.0.0.1:8000/
- API docs: http://127.0.0.1:8000/docs
- Latest metrics: http://127.0.0.1:8000/api/v1/metrics/latest

The first run downloads the configured Ultralytics YOLO weights.

## Try with a video

Edit `config.yaml`:

```yaml
camera:
  id: demo
  source: ./sample.mp4
```

For HLS, use the playlist URL directly:

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

`in` and `out` are defined by the sign change relative to the directed line from `a` to `b`. If the direction is backwards for your camera, swap `a` and `b`.

## API

### `GET /api/v1/metrics/latest`

```json
{
  "camera_id": "demo",
  "timestamp": "2026-08-19T04:30:00+00:00",
  "visible_people": 12,
  "roi_occupancy": 8,
  "flow_in": 3,
  "flow_out": 1
}
```

### `GET /api/v1/metrics/history?minutes=60`

Returns the stored metric samples for the requested lookback window.

### `GET /api/v1/events?minutes=60`

Returns individual line-crossing events (`in` / `out`).

### `GET /api/v1/preview.mjpg`

Annotated MJPEG preview for POC/debugging. Disable or remove this endpoint in deployments where video must never leave the edge device.

## Architecture

```text
Video / HLS
    |
    v
OpenCV capture
    |
    v
YOLO + ByteTrack
    |
    +--> ROI occupancy
    |
    +--> trajectory side-change --> line crossing events
    |
    v
in-memory latest state
    |
    +--> SQLite metrics/events
    |
    +--> FastAPI --> JSON API / dashboard
```

## Privacy model

The intended production architecture is **edge-first aggregation**:

1. Decode frames locally.
2. Detect and track only long enough to compute aggregate metrics.
3. Use ephemeral tracker IDs; do not create persistent person identities.
4. Do not perform face recognition.
5. Persist counts/events rather than raw frames.
6. Treat the preview endpoint as a development-only feature.

A public livestream being technically accessible does **not** automatically grant rights to reuse, republish, or commercially analyze it. Verify the stream operator's license/terms and applicable privacy rules before using a real camera feed.

## Docker

```bash
docker compose up --build
```

Mount or edit `config.yaml` before starting. GPU acceleration is intentionally not wired into the first Docker POC; CPU works for low sampling rates and a nano YOLO model.

## Scope of this POC

This version is intentionally small. Next useful steps are:

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
