# app/heatmap_render.py
from __future__ import annotations

from datetime import date
from typing import List

import numpy as np
from PIL import Image, ImageDraw

import matplotlib
matplotlib.use("Agg")  # non-interactive backend for headless Docker
import matplotlib.cm as cm
import matplotlib.colors as mcolors

from .config import settings


def _get_colormap_name() -> str:
    """
    Resolve the colormap name from settings.

    Prefers `settings.colormap`, falls back to `settings.colormap_name`,
    and defaults to 'turbo' if neither is set.
    """
    name = getattr(settings, "colormap", None) or getattr(
        settings, "colormap_name", None
    )
    return name or "turbo"


def get_colormap(name: str) -> mcolors.Colormap:
    """
    Return a matplotlib Colormap.

    Supports:
    - Any built-in matplotlib colormap (e.g. 'turbo', 'viridis', etc.)
    - Custom 'catppuccin-mocha' gradient.
    """
    key = (name or "").lower()

    if key in ("catppuccin-mocha", "catppuccin_mocha", "catppuccin"):
        # Catppuccin Mocha-inspired gradient:
        # dark -> cool -> teal/green -> warm -> red
        colors = [
            "#11111b",  # base
            "#1e1e2e",  # mantle
            "#313244",  # surface0
            "#89b4fa",  # blue
            "#94e2d5",  # teal
            "#a6e3a1",  # green
            "#f9e2af",  # yellow
            "#fab387",  # peach
            "#f38ba8",  # red (high)
        ]
        return mcolors.LinearSegmentedColormap.from_list(
            "catppuccin-mocha", colors
        )

    # Fall back to any Matplotlib colormap (including 'turbo')
    return cm.get_cmap(name)


def _prepare_data_for_color(matrix: np.ndarray) -> np.ndarray:
    """
    Prepare matrix for color mapping:

    - Cast to float
    - Treat values <= 0 as missing (set to NaN) so they render as black
      (these are long gaps in HR data from our ingest stage).
    """
    data = matrix.astype(float)
    data[data <= 0] = np.nan
    return data


def calculate_color_scale(matrix: np.ndarray) -> tuple[float, float]:
    """
    Determine vmin/vmax for the colormap using either:

    - Fixed HR range from settings.hr_min / settings.hr_max, OR
    - Robust percentiles (1st and 99th) of finite, non-missing data.

    This mirrors the behavior of the original heatmap script while
    allowing explicit overrides.
    """
    data = _prepare_data_for_color(matrix)
    finite = data[np.isfinite(data)]

    if finite.size == 0:
        return 0.0, 1.0

    # Explicit override wins
    if getattr(settings, "hr_min", None) is not None and getattr(
        settings, "hr_max", None
    ) is not None:
        return float(settings.hr_min), float(settings.hr_max)

    # Robust scale like the original script
    vmin = float(np.nanpercentile(finite, 1))
    vmax = float(np.nanpercentile(finite, 99))

    # Fallback if degenerate
    if not np.isfinite(vmin) or not np.isfinite(vmax) or vmin == vmax:
        vmin = float(np.nanmin(finite))
        vmax = float(np.nanmax(finite))
        if vmin == vmax:
            vmin, vmax = vmin - 1.0, vmax + 1.0

    return vmin, vmax


def render_heatmap_image(
    matrix: np.ndarray,
    dates: List[date],
) -> Image.Image:
    """
    Render a heatmap image from a (1440, N) matrix and date list.

    Rows = minutes of the day (0..1439)
    Columns = days (oldest..newest)

    Color mapping:
    - Uses robust percentile-based scaling (1–99th)
    - Values <= 0 are treated as missing and drawn as black
    - NaNs are also drawn as black
    """
    if matrix.shape[0] != 1440:
        raise ValueError(f"Expected 1440 rows for minutes, got {matrix.shape[0]}")

    n_days = matrix.shape[1]

    # Prepare data: treat <= 0 as missing (NaN)
    data = _prepare_data_for_color(matrix)

    # Compute color scale
    vmin, vmax = calculate_color_scale(data)

    # Colormap (with Catppuccin Mocha support)
    cmap_name = _get_colormap_name()
    cmap = get_colormap(cmap_name)

    # Clone colormap if needed so we can safely mutate it
    try:
        cmap = cmap.copy()
    except AttributeError:
        pass

    # Missing data (NaN) drawn as black, like the original script
    cmap.set_bad(color=(0.0, 0.0, 0.0, 1.0))

    # Normalize & map to RGBA
    norm = mcolors.Normalize(vmin=vmin, vmax=vmax, clip=True)
    rgba = cmap(norm(np.ma.masked_invalid(data)))  # (1440, N, 4), floats 0..1

    # Convert to uint8 RGB
    rgb = (rgba[..., :3] * 255).astype("uint8")  # (1440, N, 3)

    # Base image: 1px/min, 1px/day, then scaled up
    base = Image.fromarray(rgb, mode="RGB")
    base = base.resize(
        (settings.image_width, settings.image_height),
        resample=Image.NEAREST,
    )

    draw = ImageDraw.Draw(base)
    W, H = base.size

    # Horizontal hour lines
    if getattr(settings, "draw_hour_lines", True):
        for h in range(0, 25):
            y = round(h * H / 24)
            draw.line([(0, y), (W - 1, y)], fill=(255, 255, 255), width=1)

    # Vertical day lines
    if getattr(settings, "draw_day_lines", True) and n_days > 1:
        for i in range(1, n_days):
            x = round(i * W / n_days)
            draw.line([(x, 0), (x, H - 1)], fill=(255, 255, 255), width=1)

    # Optional: date labels could be added here if desired

    return base


def save_heatmap_png(matrix: np.ndarray, dates: List[date], path: str) -> None:
    """
    Render and save the heatmap PNG to the given path.
    """
    img = render_heatmap_image(matrix, dates)
    img.save(path, format="PNG")
