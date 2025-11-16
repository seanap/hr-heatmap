# app/config.py
import os
from dataclasses import dataclass
from datetime import time
from pathlib import Path

import pytz


@dataclass
class Settings:
    """
    Central application configuration.

    Values are pulled from environment variables with sensible defaults
    where appropriate.
    """

    # Garmin auth (required for real data)
    garmin_user: str = os.getenv("GARMIN_USER", "")
    garmin_pass: str = os.getenv("GARMIN_PASS", "")

    # Time / range
    trailing_days: int = int(os.getenv("TRAILING_DAYS", "92"))
    timezone: str = os.getenv("TIMEZONE", "UTC")

    # Data dirs
    data_root: str = os.getenv("DATA_ROOT", "/data")
    cache_dir: str = os.getenv("CACHE_DIR", "/data/cache")
    output_dir: str = os.getenv("OUTPUT_DIR", "/data/output")

    # File paths (derived from output_dir)
    @property
    def pivot_csv_path(self) -> str:
        return os.path.join(self.output_dir, "heart_rate_minutes_pivot_filled.csv")

    @property
    def heatmap_png_path(self) -> str:
        return os.path.join(self.output_dir, "hr_heatmap.png")

    @property
    def meta_json_path(self) -> str:
        return os.path.join(self.output_dir, "meta.json")

    # Plot / heatmap options
    colormap: str = os.getenv("COLORMAP_NAME", "turbo")
    image_width: int = int(os.getenv("IMAGE_WIDTH", "920"))     # ~10 px per day for 92 days
    image_height: int = int(os.getenv("IMAGE_HEIGHT", "1440"))  # 1 px per minute

    hr_min: float | None = (
        float(os.getenv("HR_MIN")) if os.getenv("HR_MIN") is not None else None
    )
    hr_max: float | None = (
        float(os.getenv("HR_MAX")) if os.getenv("HR_MAX") is not None else None
    )

    draw_hour_lines: bool = os.getenv("DRAW_HOUR_LINES", "true").lower() == "true"
    draw_day_lines: bool = os.getenv("DRAW_DAY_LINES", "true").lower() == "true"

    # Scheduler (UTC time of daily run)
    run_hour_raw: str = os.getenv("RUN_HOUR_UTC", "4")

    @property
    def run_hour_utc(self) -> time:
        """
        Daily run time in UTC as a time object.
        Env format: "4" or "04" or "04:00".
        """
        raw = str(self.run_hour_raw)
        if ":" in raw:
            hour_str, minute_str = raw.split(":", 1)
            hour = int(hour_str)
            minute = int(minute_str)
        else:
            hour = int(raw)
            minute = 0
        return time(hour=hour, minute=minute, second=0)

    # Convenience: timezone object
    @property
    def tz(self):
        """
        Return a pytz timezone object based on the configured timezone string.
        """
        return pytz.timezone(self.timezone)


# Single global settings instance
settings = Settings()
