from __future__ import annotations

import typer
import uvicorn

from .api import create_app
from .config import load_config

app = typer.Typer(help="FlowCam: camera stream to anonymous foot-traffic metrics")


@app.command()
def run(
    config: str = typer.Option("config.yaml", "--config", "-c", help="Path to YAML config"),
) -> None:
    cfg = load_config(config)
    uvicorn.run(create_app(cfg), host=cfg.server.host, port=cfg.server.port)


if __name__ == "__main__":
    app()
