# app/garmin_client.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Dict, List

from garminconnect import (
    Garmin,
    GarminConnectAuthenticationError,
    GarminConnectConnectionError,
    GarminConnectTooManyRequestsError,
)

from .config import settings


@dataclass
class Sample:
    """Single heart-rate sample at a specific UTC timestamp."""
    timestamp: datetime  # UTC
    hr: int


class GarminClient:
    """
    Thin wrapper around python-garminconnect.

    - Uses username/password from settings
    - Calls client.get_heart_rates('YYYY-MM-DD')
    - Returns heart-rate samples as a list[Sample]
    """

    def __init__(self, cache_dir: Path | str | None = None) -> None:
        self.cache_dir = Path(cache_dir or settings.cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._client: Garmin | None = None

    # ---------- auth / low-level client ----------

    def login(self) -> None:
        """
        Log into Garmin Connect using GARMIN_USER / GARMIN_PASS.

        Creates a Garmin() client and performs the login call.
        """
        if not settings.garmin_user or not settings.garmin_pass:
            raise RuntimeError("GARMIN_USER and GARMIN_PASS must be set")

        try:
            # Fresh client each time for now; we can add cookie/session caching later.
            self._client = Garmin(settings.garmin_user, settings.garmin_pass)
            self._client.login()
        except (
            GarminConnectAuthenticationError,
            GarminConnectConnectionError,
            GarminConnectTooManyRequestsError,
        ) as err:
            raise RuntimeError(f"Garmin login failed: {err}") from err

    @property
    def client(self) -> Garmin:
        """
        Convenience accessor: ensures we're logged in before use.
        """
        if self._client is None:
            self.login()
        return self._client

    # ---------- high-level HR API ----------

    def fetch_daily_hr(self, day: date) -> List[Sample]:
        """
        Fetch raw heart-rate samples for a single day.

        Uses python-garminconnect's:
            client.get_heart_rates('YYYY-MM-DD')

        Typical response includes a 'heartRateValues' key with a list of
        [timestamp_ms, bpm] entries. We convert that into a list[Sample].
        """
        day_str = day.strftime("%Y-%m-%d")

        raw = self.client.get_heart_rates(day_str) or {}
        values = raw.get("heartRateValues") or []

        samples: List[Sample] = []

        for entry in values:
            # Expected shape: [timestamp_ms, bpm]
            if not isinstance(entry, (list, tuple)) or len(entry) != 2:
                continue

            ts_ms, hr = entry
            if hr is None:
                continue

            try:
                ts = datetime.fromtimestamp(ts_ms / 1000.0, tz=timezone.utc)
                samples.append(Sample(timestamp=ts, hr=int(hr)))
            except Exception:
                # Skip any weird entries rather than blowing up
                continue

        return samples

    def fetch_range_hr(self, start: date, end: date) -> Dict[date, List[Sample]]:
        """
        Fetch all-day HR samples for each date in [start, end].

        Returns a dict mapping date -> list[Sample].
        """
        result: Dict[date, List[Sample]] = {}
        current = start
        while current <= end:
            result[current] = self.fetch_daily_hr(current)
            current = date.fromordinal(current.toordinal() + 1)
        return result
