# FlowCam E2E Skill

Use this skill when asked to verify FlowCam end-to-end, diagnose why the pipeline is not producing metrics, or validate a new camera source.

## Goal

Prove the complete data path works:

```text
Video / HLS / RTSP
  -> FrameSource
  -> YOLO + ByteTrack
  -> FlowAnalytics
  -> MetricSample / CrossingEvent
  -> SQLite
  -> FastAPI
  -> Dashboard / JSON API
```

The E2E is successful only when the source is decoded, people are detected/tracked, analytics change, and the same resulting data is observable through persistence and API surfaces.

## Rules

- Use the repository's uv workflow. Do not create ad-hoc pip environments.
- Respect `uv.lock`; use `--frozen` unless intentionally changing dependencies.
- Start with a local prerecorded video before debugging a remote live stream.
- Do not introduce unrelated refactors while diagnosing E2E failures.
- Do not repeatedly run lint/build/test after every tiny edit. Run targeted checks while iterating, then one full validation pass at the end.
- Do not assume a normal YouTube watch URL is a directly decodable video source.
- Public accessibility of a livestream does not imply permission for redistribution or commercial analysis. Use sources whose terms permit the intended test.
- Do not persist raw frames as part of the normal E2E path. The MJPEG preview is development-only.

## Phase 0: environment validation

From the repository root:

```bash
uv sync --frozen --all-groups
uv run python --version
```

Confirm Python is the version pinned by `.python-version`.

Run the static/unit baseline once:

```bash
uv run ruff check .
uv run ruff format --check .
uv run ty check src tests
uv run pytest
```

If these fail, fix them before E2E unless the failure is clearly unrelated to runtime behavior.

### Optional CUDA check

If GPU inference is intended:

```bash
uv run python -c "import torch; print(torch.cuda.is_available()); print(torch.cuda.get_device_name(0) if torch.cuda.is_available() else None)"
```

Expected result on a CUDA-capable machine:

```text
True
<GPU name>
```

Set this in the config when CUDA is available:

```yaml
inference:
  device: "0"
```

Otherwise leave `device: null` and run on CPU.

## Phase 1: local-video E2E

Always prove the local path before using a remote camera.

### 1. Prepare a source

Place a short pedestrian video at:

```text
./sample.mp4
```

A useful test video should contain:

- multiple visible people
- several people crossing the intended counting line
- at least 30 seconds of footage
- modest occlusion, but not an extreme crowd for the first test

### 2. Prepare configuration

Copy the example config:

```bash
cp config.example.yaml config.yaml
```

Use a known-simple configuration:

```yaml
camera:
  id: local-e2e
  source: ./sample.mp4
  reconnect_seconds: 1

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
      - [0.05, 0.05]
      - [0.95, 0.05]
      - [0.95, 0.95]
      - [0.05, 0.95]

  crossing_line:
    id: entrance
    a: [0.50, 0.05]
    b: [0.50, 0.95]

  track_ttl_seconds: 5

storage:
  sqlite_path: ./data/e2e.db
  flush_interval_seconds: 1

server:
  host: 127.0.0.1
  port: 8000
```

Coordinates are normalized to `[0, 1]`:

```text
(0,0) ---------------- (1,0)
  |                       |
  |                       |
  |                       |
(0,1) ---------------- (1,1)
```

For a vertical center line:

```yaml
crossing_line:
  a: [0.5, 0.0]
  b: [0.5, 1.0]
```

Swap `a` and `b` if `in` and `out` are reversed.

### 3. Start FlowCam

```bash
uv run flowcam run --config config.yaml
```

The first inference run may download the configured Ultralytics model weights.

### 4. Verify HTTP surfaces

Health:

```bash
curl http://127.0.0.1:8000/healthz
```

Expected shape:

```json
{
  "status": "ok",
  "camera_id": "local-e2e"
}
```

Latest metric:

```bash
curl http://127.0.0.1:8000/api/v1/metrics/latest
```

Expected shape:

```json
{
  "camera_id": "local-e2e",
  "timestamp": "...",
  "visible_people": 7,
  "roi_occupancy": 6,
  "flow_in": 4,
  "flow_out": 2
}
```

Crossing events:

```bash
curl "http://127.0.0.1:8000/api/v1/events?minutes=60"
```

Expected shape after a crossing:

```json
[
  {
    "camera_id": "local-e2e",
    "line_id": "entrance",
    "track_id": 14,
    "direction": "in",
    "timestamp": "..."
  }
]
```

Metrics history:

```bash
curl "http://127.0.0.1:8000/api/v1/metrics/history?minutes=60"
```

### 5. Verify the dashboard

Open:

```text
http://127.0.0.1:8000/
```

Check all of the following:

- annotated preview is visible
- people receive bounding boxes / tracking annotations
- `Visible` changes as people enter and leave the frame
- `ROI occupancy` changes correctly
- `Flow in` / `Flow out` increments when people cross the configured line

### 6. Verify SQLite

If `sqlite3` is installed:

```bash
sqlite3 data/e2e.db
```

Then:

```sql
SELECT *
FROM metrics
ORDER BY timestamp DESC
LIMIT 10;

SELECT *
FROM crossing_events
ORDER BY timestamp DESC
LIMIT 10;
```

The persisted values should agree with the API state/history.

## Phase 2: compare against manual ground truth

A technically running pipeline is not enough. Measure counting quality.

Select a 30-60 second segment and manually count people crossing the configured line.

Record:

```text
manual_count = N
flowcam_count = M
absolute_error = |M - N|
relative_error = |M - N| / N
```

For an initial POC, a useful target is roughly within 10% on a non-extreme scene. Treat this as a practical POC target, not a universal accuracy guarantee.

If the error is large, inspect:

- missed detections
- duplicate track IDs
- ID switches under occlusion
- line placement
- sampling FPS
- confidence threshold
- camera perspective
- people walking close to or along the line

## Phase 3: remote live-camera E2E

Only move to a remote source after Phase 1 succeeds.

Use a direct media source that OpenCV/FFmpeg can decode, for example:

- `.m3u8` HLS playlist
- RTSP URL
- direct MP4 stream/file
- another FFmpeg/OpenCV-compatible media URL

Do not use a regular page URL such as:

```text
https://youtube.com/watch?v=...
```

unless a separate adapter resolves that page to a permitted direct media stream.

Configure:

```yaml
camera:
  id: public-live
  source: https://example.com/live/index.m3u8
```

Then run the same checks as Phase 1:

```bash
uv run flowcam run --config config.yaml
curl http://127.0.0.1:8000/healthz
curl http://127.0.0.1:8000/api/v1/metrics/latest
```

## Remote-source troubleshooting order

When a live source fails, isolate layers in this order.

### 1. Can FFmpeg/OpenCV decode it?

Use ffprobe when available:

```bash
ffprobe -hide_banner "<source-url>"
```

If FFmpeg cannot decode it, do not debug YOLO or analytics yet.

### 2. Is the source stable?

Check for:

- expiring/signed URLs
- redirects
- cookies/authentication
- referer/user-agent requirements
- HLS playlist refresh behavior
- temporary network failures

### 3. Are frames reaching inference?

If the preview is visible but metrics stay zero, inspect detector confidence and scene scale.

Try a lower confidence for diagnosis:

```yaml
inference:
  confidence: 0.20
```

Do not leave a low threshold permanently without checking false positives.

### 4. Are people detected but not counted crossing?

If `visible_people > 0` but flow counts remain zero:

- confirm the line visibly intersects pedestrian trajectories
- ensure the same track ID survives across the line
- increase `sample_fps` if crossing motion is skipped
- inspect whether the line direction needs reversing

## Definition of done

An E2E run is complete when all of these are demonstrated:

```text
[ ] source decodes continuously
[ ] person detections are visible
[ ] tracker IDs persist long enough for movement analysis
[ ] ROI occupancy changes plausibly
[ ] line crossing produces in/out events
[ ] latest metrics API changes
[ ] history API contains persisted samples
[ ] crossing events are persisted in SQLite
[ ] dashboard displays the same live state
[ ] manual count vs FlowCam count has been recorded
```

Report the final result with:

```text
Source:
Duration tested:
Device (CPU/GPU):
Average visible people:
Manual crossings:
FlowCam crossings:
Relative error:
Observed failures:
Config changes made:
Overall E2E status: PASS / PARTIAL / FAIL
```

## Final validation after changes

After fixing E2E issues, run one complete repository validation pass:

```bash
uv run ruff check .
uv run ruff format --check .
uv run ty check src tests
uv run pytest
```

Do not claim the E2E is successful if only unit/static checks pass; the runtime source-to-API path must also have been exercised.
