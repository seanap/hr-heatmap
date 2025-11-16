# app/pivot_builder.py
from __future__ import annotations

import csv
from datetime import date, timedelta
from pathlib import Path
import numpy as np

from .hr_ingest import build_daily_table
from .garmin_client import GarminClient
from .config import settings


def build_table_for_last_n_days(
    n: int,
    tz_name: str | None = None,  # kept for compatibility with orchestrator
) -> tuple[np.ndarray, list[date]]:
    """
    Fetch heart rate samples for last n days (including today),
    return (1440×N matrix, ordered list of dates).
    """
    today = date.today()
    start = today - timedelta(days=n - 1)

    client = GarminClient(cache_dir=settings.cache_dir)
    client.login()

    # Fetch daily samples
    daily_data = client.fetch_range_hr(start, today)

    matrix, dates = build_daily_table(daily_data)

    return matrix, dates


def write_pivot_csv(matrix: np.ndarray, dates: list[date], csv_path: str | Path) -> None:
    """
    Write the canonical CSV table:
    time_utc, YYYY-MM-DD, YYYY-MM-DD, ...
    """
    csv_path = Path(csv_path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)

    with csv_path.open("w", newline="") as f:
        writer = csv.writer(f)

        # Header
        header = ["time_local"] + [d.isoformat() for d in dates]
        writer.writerow(header)

        # Rows: HH:MM, hr_day1, hr_day2, ...
        for minute in range(1440):
            hh = minute // 60
            mm = minute % 60
            time_str = f"{hh:02d}:{mm:02d}"
            row = [time_str] + list(matrix[minute, :])
            writer.writerow(row)


def load_pivot(csv_path: str | Path) -> tuple[np.ndarray, list[str]]:
    """
    Read pivot CSV back into matrix + date headers (not often needed).
    """
    csv_path = Path(csv_path)
    with csv_path.open("r") as f:
        rows = list(csv.reader(f))

    header = rows[0][1:]  # skip time_local
    matrix = np.array([[float(x) for x in row[1:]] for row in rows[1:]])
    return matrix, header
