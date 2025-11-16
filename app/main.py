# app/main.py
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, time as dtime
from pathlib import Path

from fastapi import FastAPI, Response
from fastapi.responses import FileResponse, JSONResponse

from .config import settings
from .orchestrator import run_full_pipeline, load_status


app = FastAPI(title="HR Heatmap Service")


def _next_run_time_utc(now: datetime) -> datetime:
    """Compute the next daily run time in UTC (very simple scheduler)."""
    target = now.replace(
        hour=settings.run_hour_utc.hour,
        minute=settings.run_hour_utc.minute,
        second=settings.run_hour_utc.second,
        microsecond=0,
    )
    if target <= now:
        target = target + timedelta(days=1)
    return target


async def scheduler_loop():
    """
    Background task: run the pipeline once at startup (if needed),
    then once per day at the configured time.
    """
    # Initial run (you can add staleness checks if desired)
    try:
        run_full_pipeline()
    except Exception as e:
        # In a real implementation, log this error
        print(f"[scheduler] Initial pipeline run failed: {e}")

    while True:
        now = datetime.utcnow()
        nxt = _next_run_time_utc(now)
        sleep_seconds = (nxt - now).total_seconds()
        await asyncio.sleep(max(sleep_seconds, 60))  # at least 60s

        try:
            run_full_pipeline()
        except Exception as e:
            print(f"[scheduler] Daily pipeline run failed: {e}")


@app.on_event("startup")
async def startup_event():
    # Ensure dirs exist
    Path(settings.output_dir).mkdir(parents=True, exist_ok=True)
    # Kick off scheduler
    asyncio.create_task(scheduler_loop())


@app.get("/heatmap.png")
async def get_heatmap():
    """
    Serve the latest heatmap PNG. If missing, attempt a rebuild.
    """
    if not Path(settings.heatmap_png_path).exists():
        try:
            run_full_pipeline()
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={"error": "Failed to generate heatmap", "detail": str(e)},
            )

    return FileResponse(settings.heatmap_png_path, media_type="image/png")


@app.get("/status")
async def get_status():
    """
    Return last-run info and some metadata.
    """
    status = load_status()
    now = datetime.utcnow()
    status["now_utc"] = now.isoformat() + "Z"
    status["next_run_utc"] = _next_run_time_utc(now).isoformat() + "Z"
    return status


@app.post("/force-rebuild")
async def force_rebuild():
    """
    Manually trigger a full pipeline run.
    """
    try:
        status = run_full_pipeline()
        return status
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": "Failed to rebuild", "detail": str(e)},
        )
