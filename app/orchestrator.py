# app/orchestrator.py
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

import numpy as np

from .config import settings
from .pivot_builder import build_table_for_last_n_days, write_pivot_csv
from .heatmap_render import save_heatmap_png


def run_full_pipeline() -> Dict[str, Any]:
    """
    Fetch data from Garmin, build 1440xN table, write CSV and PNG,
    and update meta.json.

    Returns a simple status dict.
    """
    Path(settings.output_dir).mkdir(parents=True, exist_ok=True)

    # 1. Build matrix + date list
    matrix, dates = build_table_for_last_n_days(
        settings.trailing_days, settings.timezone
    )

    # 2. Persist pivot CSV
    write_pivot_csv(matrix, dates, settings.pivot_csv_path)

    # 3. Render heatmap PNG
    save_heatmap_png(matrix, dates, settings.heatmap_png_path)

    # 4. Save meta
    status = {
        "last_run_utc": datetime.utcnow().isoformat() + "Z",
        "num_days": len(dates),
        "first_day": dates[0].isoformat() if dates else None,
        "last_day": dates[-1].isoformat() if dates else None,
        "trailing_days_requested": settings.trailing_days,
    }

    with open(settings.meta_json_path, "w", encoding="utf-8") as f:
        json.dump(status, f, indent=2)

    return status


def load_status() -> Dict[str, Any]:
    """
    Read meta.json if present, else return a default structure.
    """
    try:
        with open(settings.meta_json_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {
            "last_run_utc": None,
            "num_days": 0,
            "first_day": None,
            "last_day": None,
            "trailing_days_requested": settings.trailing_days,
        }
