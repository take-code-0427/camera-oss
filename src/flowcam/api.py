from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse, StreamingResponse

from .config import AppConfig
from .engine import FlowEngine
from .sources import OpenCVFrameSource
from .storage import SQLiteMetricsSink
from .tracking import UltralyticsPersonTracker

DASHBOARD_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width,initial-scale=1" />
<title>FlowCam</title>
<style>
body{font-family:system-ui,sans-serif;margin:0;background:#111;color:#eee}main{max-width:1100px;margin:auto;padding:24px}.cards{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}.card{background:#1d1d1d;padding:18px;border-radius:12px}.value{font-size:2rem;font-weight:700}img{width:100%;margin-top:18px;border-radius:12px;background:#222}@media(max-width:700px){.cards{grid-template-columns:repeat(2,1fr)}}
</style>
</head>
<body><main><h1>FlowCam POC</h1><div class="cards">
<div class="card">Visible<div id="visible" class="value">-</div></div>
<div class="card">ROI occupancy<div id="roi" class="value">-</div></div>
<div class="card">Flow in<div id="in" class="value">-</div></div>
<div class="card">Flow out<div id="out" class="value">-</div></div>
</div><img src="/api/v1/preview.mjpg" alt="annotated preview" /></main>
<script>
async function refresh(){try{const r=await fetch('/api/v1/metrics/latest');const m=await r.json();visible.textContent=m.visible_people;roi.textContent=m.roi_occupancy;document.getElementById('in').textContent=m.flow_in;out.textContent=m.flow_out}catch(e){console.error(e)}}refresh();setInterval(refresh,1000);
</script></body></html>"""


def create_app(config: AppConfig) -> FastAPI:
    source = OpenCVFrameSource(config.camera.source)
    tracker = UltralyticsPersonTracker(config.inference)
    sink = SQLiteMetricsSink(config.storage.sqlite_path)
    engine = FlowEngine(config, source=source, tracker=tracker, sink=sink)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        await engine.start()
        try:
            yield
        finally:
            await engine.stop()

    app = FastAPI(title="FlowCam", version="0.1.0", lifespan=lifespan)
    app.state.sink = sink
    app.state.engine = engine

    @app.get("/", response_class=HTMLResponse)
    async def dashboard() -> str:
        return DASHBOARD_HTML

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok", "camera_id": config.camera.id}

    @app.get("/api/v1/metrics/latest")
    async def latest() -> dict[str, str | int]:
        return engine.snapshot_metric().as_record()

    @app.get("/api/v1/metrics/history")
    async def history(minutes: int = Query(60, ge=1, le=10080)) -> list[dict[str, object]]:
        since = datetime.now(timezone.utc) - timedelta(minutes=minutes)
        return await asyncio.to_thread(sink.history, since.isoformat())

    @app.get("/api/v1/events")
    async def events(minutes: int = Query(60, ge=1, le=10080)) -> list[dict[str, object]]:
        since = datetime.now(timezone.utc) - timedelta(minutes=minutes)
        return await asyncio.to_thread(sink.events, since.isoformat())

    async def mjpeg():
        while True:
            jpeg = engine.snapshot_jpeg()
            if jpeg:
                yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + jpeg + b"\r\n"
            await asyncio.sleep(0.1)

    @app.get("/api/v1/preview.mjpg")
    async def preview() -> StreamingResponse:
        return StreamingResponse(mjpeg(), media_type="multipart/x-mixed-replace; boundary=frame")

    return app
