# app/hr_ingest.py
from __future__ import annotations

import numpy as np
import pandas as pd
from datetime import datetime
from typing import List, Tuple, Dict

from .garmin_client import Sample
from .config import settings


def samples_to_local_minutes(samples: List[Sample]) -> Dict[int, List[int]]:
    """
    Convert raw timestamp samples to a dict:
        minute_of_day -> list of HR samples (ints)

    Applies:
    - Local timezone conversion
    - Floor to lower minute
    """
    tz = settings.tz
    minute_map: Dict[int, List[int]] = {}

    for s in samples:
        # 1. Convert UTC timestamp -> local timezone
        local_ts = s.timestamp.astimezone(tz)

        # 2. Floor to lower minute
        floored = local_ts.replace(second=0, microsecond=0)

        # 3. Compute minute-of-day
        minute_of_day = floored.hour * 60 + floored.minute

        if minute_of_day not in minute_map:
            minute_map[minute_of_day] = []

        minute_map[minute_of_day].append(s.hr)

    return minute_map


def build_daily_minute_series(samples: List[Sample], max_gap: int = 10) -> np.ndarray:
    """
    Build the 1440-sample vector for one day.

    Steps:
    - Convert timestamps → minute_of_day
    - Aggregate per minute (mean)
    - Interpolate gaps <= max_gap minutes
    - Leave long gaps as NaN
    - Replace NaN with 0 at the end (per user spec)
    """
    # 1440 minutes/day
    arr = np.full(1440, np.nan, dtype=float)

    minute_map = samples_to_local_minutes(samples)

    # Fill known minutes with mean HR
    for minute, vals in minute_map.items():
        if vals:
            arr[minute] = np.mean(vals)

    # --- Interpolate gaps up to max_gap minutes ---
    # Use pandas Series for easy interpolation
    s = pd.Series(arr)

    # Interpolate *only inside gaps* and limit gap size
    s_interpolated = s.interpolate(
        method="linear",
        limit=max_gap,
        limit_direction="both"
    )

    # Convert to numpy
    arr_interp = s_interpolated.to_numpy()

    # --- Replace remaining NaNs with 0 (your spec) ---
    # These represent longer than max_gap gaps
    arr_interp = np.nan_to_num(arr_interp, nan=0.0)

    return arr_interp


def build_daily_table(
    daily_data: Dict[datetime.date, List[Sample]],
    tz=None
) -> Tuple[np.ndarray, List[datetime.date]]:
    """
    Convert dict[date -> samples] into:
        (1440 × N matrix, sorted_dates)

    Where each column = one day vector.
    """
    sorted_dates = sorted(daily_data.keys())
    cols = []

    for d in sorted_dates:
        series = build_daily_minute_series(daily_data[d], max_gap=10)
        cols.append(series)

    if len(cols) == 0:
        # Return empty table if nothing exists
        return np.zeros((1440, 0)), []

    matrix = np.column_stack(cols)  # shape = (1440, N)

    return matrix, sorted_dates
