# app/heatmap_render.py
from __future__ import annotations

from datetime import date
from typing import List

import numpy as np
from PIL import Image, ImageDraw
import matplotlib
matplotlib.use("Agg")
import matplotlib.cm as cm
import matplotlib.colors as mcolors

from .config import settings


def calculate_color_scale(matrix: np.ndarray) -> tuple[float, float]:
    """
    Determine vmin/vmax for the colormap using either fixed HR range
    or robust percentiles.
    """
    finite = matrix[np.isfinite(matrix)]
    if finite.size == 0:
        return 0.0, 1.0

    if settings.hr_min is not None and settings.hr_max is not None:
        return settings.hr_min, settings.hr_max

    vmin = float(np.nanpercentile(finite, 1))
    vmax = float(np.nanpercentile(finite, 99))
    if vmin == vmax:
        vmin, vmax = vmin - 1.0, vmax + 1.0
    return vmin, vmax


def render_heatmap_image(
    matrix: np.ndarray,
    dates: List[date],
) -> Image.Image:
    """
    Render a heatmap image from a (1440, N) matrix and date list.
    """
    if matrix.shape[0] != 1440:
        raise ValueError(f"Expected 1440 rows for minutes, got {matrix.shape[0]}")

    n_days = matrix.shape[1]

    vmin, vmax = calculate_color_scale(matrix)
    cmap = cm.get_cmap(settings.colormap)
    norm = mcolors.Normalize(vmin=vmin, vmax=vmax, clip=True)

    rgba = cmap(norm(np.ma.masked_invalid(matrix)))
    rgb = (rgba[..., :3] * 255).astype("uint8")  # (1440, N, 3)

    # Create base image with 1px/min, 1px/day then scale
    base = Image.fromarray(rgb, mode="RGB")
    base = base.resize(
        (settings.image_width, settings.image_height),
        resample=Image.NEAREST,
    )

    draw = ImageDraw.Draw(base)
    W, H = base.size

    if settings.draw_hour_lines:
        for h in range(0, 25):
            y = round(h * H / 24)
            draw.line([(0, y), (W - 1, y)], fill=(255, 255, 255), width=1)

    if settings.draw_day_lines and n_days > 1:
        for i in range(1, n_days):
            x = round(i * W / n_days)
            draw.line([(x, 0), (x, H - 1)], fill=(255, 255, 255), width=1)

    # TODO: Add optional date labels if you want them.

    return base


def save_heatmap_png(matrix: np.ndarray, dates: List[date], path: str) -> None:
    img = render_heatmap_image(matrix, dates)
    img.save(path, format="PNG")
