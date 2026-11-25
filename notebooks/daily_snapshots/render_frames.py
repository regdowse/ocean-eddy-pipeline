#!/usr/bin/env python3
"""Render SEACOFS daily overlays without running the dataset pipeline."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.patheffects as pe
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
import netCDF4 as nc
import numpy as np
import pandas as pd
from PIL import Image

# Allow direct invocation from a source checkout, including from another cwd.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "src"))
from seacofs_eddy_dataset.config import load_config
from seacofs_eddy_dataset.core.grid import read_reference_grid
from seacofs_eddy_dataset.core.velocity import rotate_uv
from seacofs_eddy_dataset.stages.detection import find_model_files, reference_grid_path


def arguments():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=PROJECT_ROOT / "config/local.yaml")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--processed-path", type=Path, help="Override the processed surface table")
    start = parser.add_mutually_exclusive_group()
    start.add_argument("--start-day", type=int)
    start.add_argument("--start-date", help="Inclusive YYYY-MM-DD")
    end = parser.add_mutually_exclusive_group()
    end.add_argument("--end-day", type=int)
    end.add_argument("--end-date", help="Inclusive YYYY-MM-DD")
    parser.add_argument("--overwrite", action="store_true", help="Redraw existing selected frames")
    parser.add_argument("--speed-vmax", type=float, default=1.377, help="Fixed colour maximum, m/s")
    parser.add_argument("--dpi", type=int, default=150, help="9 by 10 inches; default 1350 by 1500 px")
    parser.add_argument("--quiver-step", type=int, default=12)
    parser.add_argument("--quiver-scale", type=float, default=13.2,
                        help="Fixed arrow scale; 13.2 approximates the old automatic scale")
    parser.add_argument("--no-quiver", action="store_true")
    parser.add_argument("--no-labels", action="store_true")
    args = parser.parse_args()
    for name in ("speed_vmax", "dpi", "quiver_step", "quiver_scale"):
        if not np.isfinite(getattr(args, name)) or getattr(args, name) <= 0:
            parser.error(f"--{name.replace('_', '-')} must be positive and finite")
    return args


def ellipse_vertices(row, unit_circle):
    """The same level as the notebook: (x-c)' Q (x-c) = Rc**2 / 2."""
    if not np.all(np.isfinite([row.xc, row.yc, row.q11, row.q12, row.q22, row.Rc])):
        return None
    if row.Rc <= 0:
        return None
    values, vectors = np.linalg.eigh([[row.q11, row.q12], [row.q12, row.q22]])
    if np.any(values <= 0):
        return None
    radii = row.Rc / np.sqrt(2 * values)
    return (unit_circle * radii) @ vectors.T + [row.xc, row.yc]


class FrameRenderer:
    """Keep static artists and axes positions fixed; update only daily data."""

    def __init__(self, grid, args):
        self.grid, self.args = grid, args
        self.fig, self.ax = plt.subplots(figsize=(9, 10), dpi=args.dpi, constrained_layout=True)
        ax = self.ax
        self.mesh = ax.pcolormesh(
            grid.X_grid, grid.Y_grid, np.zeros_like(grid.X_grid), shading="auto",
            vmin=0, vmax=args.speed_vmax, cmap="Blues_r",
        )
        self.fig.colorbar(self.mesh, ax=ax, label=r"Current speed (ms$^{-1}$)", shrink=0.7)
        self.quiver = None
        if not args.no_quiver:
            step = args.quiver_step
            self.quiver = ax.quiver(
                grid.X_grid[::step, ::step], grid.Y_grid[::step, ::step],
                np.zeros_like(grid.X_grid[::step, ::step]),
                np.zeros_like(grid.Y_grid[::step, ::step]),
                color="0.2", alpha=0.55, pivot="mid", width=0.0015, scale=args.quiver_scale,
            )
        self.ellipses = LineCollection([], linewidths=1.5, zorder=9)
        ax.add_collection(self.ellipses)
        self.ellipses.set_clip_path(ax.patch)
        self.centres = ax.scatter([], [], edgecolor="black", linewidth=0.8, s=20, zorder=10)
        self.labels = []
        angles = np.linspace(0, 2 * np.pi, 257)
        self.unit_circle = np.column_stack((np.cos(angles), np.sin(angles)))
        for field, levels, fmt in (
            (grid.lat_rho, [-40, -35, -30, -25], lambda value: f"{abs(value):.0f}°S"),
            (grid.lon_rho, [150, 155, 160], lambda value: f"{value:.0f}°E"),
        ):
            contours = ax.contour(grid.X_grid, grid.Y_grid, field, levels=levels,
                                  colors="black", linewidths=0.5, alpha=0.7)
            ax.clabel(contours, fmt=fmt, fontsize=8)
        ax.set(xlabel="x (km)", ylabel="y (km)",
               title="26yr SEACOFS eddies | Day 0000 | 2000-01-01 | AE=0, CE=0",
               xlim=(grid.x_grid.min(), grid.x_grid.max()),
               ylim=(grid.y_grid.min(), grid.y_grid.max()), aspect="equal")
        ax.autoscale(False)
        # Solve the familiar notebook layout once, without daily labels, then freeze it.
        self.fig.canvas.draw()
        positions = [axes.get_position().frozen() for axes in self.fig.axes]
        self.fig.set_layout_engine("none")
        for axes, position in zip(self.fig.axes, positions):
            axes.set_position(position)

    def render(self, u, v, rows, day, date, path, signature):
        self.mesh.set_array(np.ma.masked_invalid(np.hypot(u, v)).ravel())
        if self.quiver is not None:
            step = self.args.quiver_step
            self.quiver.set_UVC(u[::step, ::step], v[::step, ::step])
        colours = [{"AE": "red", "CE": "cyan"}.get(cyc, "white") for cyc in rows.Cyc]
        self.centres.set_offsets(rows[["xc", "yc"]].to_numpy(dtype=float).reshape(-1, 2))
        self.centres.set_facecolors(colours)
        segments, edge_colours = [], []
        for row, colour in zip(rows.itertuples(index=False), colours):
            vertices = ellipse_vertices(row, self.unit_circle)
            if vertices is not None:
                segments.append(vertices)
                edge_colours.append(colour)
        self.ellipses.set_segments(segments)
        self.ellipses.set_colors(edge_colours)
        if not self.args.no_labels:
            while len(self.labels) < len(rows):
                label = self.ax.annotate(
                    "", (0, 0), textcoords="offset points", xytext=(3, 3), fontsize=8,
                    color="white", weight="bold",
                    path_effects=[pe.withStroke(linewidth=2, foreground="black")],
                    zorder=11, clip_on=True, annotation_clip=True,
                )
                label.set_clip_path(self.ax.patch)
                label.set_in_layout(False)
                self.labels.append(label)
            for label, row in zip(self.labels, rows.itertuples(index=False)):
                label.xy = (row.xc, row.yc)
                label.set_text(str(int(row.Eddy)))
                label.set_visible(True)
            for label in self.labels[len(rows):]:
                label.set_visible(False)
        ae, ce = counts(rows)
        self.ax.set_title(
            f"26yr SEACOFS eddies | Day {day} | {date:%Y-%m-%d} | AE={ae}, CE={ce}"
        )
        temporary = path.with_suffix(".png.tmp")
        self.fig.savefig(temporary, format="png", dpi=self.args.dpi, facecolor="white",
                         metadata={"render_signature": signature})
        temporary.replace(path)

    def close(self):
        plt.close(self.fig)


def counts(rows):
    return int(rows.Cyc.eq("AE").sum()), int(rows.Cyc.eq("CE").sum())


def main():
    args = arguments()
    config = load_config(args.config)
    origin = pd.Timestamp(config.raw.get("processing", {}).get("date_origin", "1990-01-01"))
    start, end = args.start_day, args.end_day
    if args.start_date:
        start = (pd.Timestamp(args.start_date).normalize() - origin).days
    if args.end_date:
        end = (pd.Timestamp(args.end_date).normalize() - origin).days
    if start is not None and end is not None and start > end:
        raise ValueError("Start must be on or before end")
    processed = (args.processed_path or config.output_root / "processed/eddy_dataset_processed.parquet").resolve()
    output = (args.output_dir or config.output_root / "daily_overlay_frames").resolve()
    df = pd.read_parquet(processed, columns=["Eddy", "Day", "Cyc", "xc", "yc", "q11", "q12", "q22", "Rc"])
    df = df.sort_values(["Day", "Eddy"])
    by_day = {int(day): rows for day, rows in df.groupby("Day", sort=False)}
    empty = df.iloc[:0]
    # Index time metadata first; detect duplicates and sort before any image writes.
    selected = []
    seen = set()
    paths = find_model_files(config)
    for path in paths:
        with nc.Dataset(path) as dataset:
            days = np.rint(np.asarray(dataset["ocean_time"][:], dtype=float) / 86400).astype(int)
        for index, value in enumerate(days):
            day = int(value)
            if (start is not None and day < start) or (end is not None and day > end):
                continue
            if day in seen:
                raise ValueError(f"Duplicate model day: {day}")
            seen.add(day)
            selected.append((day, path, index))
    selected.sort(key=lambda item: item[0])
    if not selected:
        raise ValueError("No model days match the requested range")
    missing = sorted(set(range(selected[0][0], selected[-1][0] + 1)) - seen)
    if missing:
        print(f"Warning: {len(missing)} model days are missing within the selected range", flush=True)
    grid_path = reference_grid_path(config)

    def identity(path):
        stat = path.stat()
        return {"path": str(path.resolve()), "size": stat.st_size, "mtime_ns": stat.st_mtime_ns}
    settings = {
        "renderer_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "config_sha256": hashlib.sha256(config.config_path.read_bytes()).hexdigest(),
        "processed": identity(processed), "grid": identity(grid_path),
        "model_root": str(config.model_root.resolve()),
        "speed_vmax": args.speed_vmax, "dpi": args.dpi, "figsize": [9, 10],
        "quiver_step": args.quiver_step, "quiver_scale": args.quiver_scale,
        "labels": not args.no_labels, "quiver": not args.no_quiver,
        "matplotlib": matplotlib.__version__,
    }
    output.mkdir(parents=True, exist_ok=True)
    settings_path = output / "render_settings.json"
    if not args.overwrite and any(output.glob("frame_day_*.png")):
        if not settings_path.exists() or json.loads(settings_path.read_text()) != settings:
            raise ValueError("Existing frame settings differ or are unknown; use a new output directory or --overwrite")
    temporary_settings = settings_path.with_suffix(".json.tmp")
    temporary_settings.write_text(json.dumps(settings, indent=2) + "\n")
    temporary_settings.replace(settings_path)
    renderer = None
    source = None
    source_path = None
    manifest = output / "frame_manifest.csv"
    temporary_manifest = manifest.with_suffix(".csv.tmp")
    written = 0
    try:
        with temporary_manifest.open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=[
                "frame", "day", "date", "source_file", "time_index", "frame_path", "AE", "CE", "status",
            ])
            writer.writeheader()
            for number, (day, path, index) in enumerate(selected):
                frame = output / f"frame_day_{day:05d}.png"
                rows = by_day.get(day, empty)
                date = origin + pd.Timedelta(days=day)
                signature = hashlib.sha256(json.dumps(
                    {"settings": settings, "source": identity(path), "day": day, "index": index},
                    sort_keys=True,
                ).encode()).hexdigest()
                status = "skipped"
                if frame.exists() and not args.overwrite:
                    with Image.open(frame) as image:
                        if (image.info.get("render_signature") != signature
                                or image.size != (9 * args.dpi, 10 * args.dpi)):
                            raise ValueError(f"Frame provenance differs: {frame}; use --overwrite")
                        image.verify()
                if args.overwrite or not frame.exists():
                    if renderer is None:
                        renderer = FrameRenderer(read_reference_grid(grid_path), args)
                    if path != source_path:
                        if source is not None:
                            source.close()
                        source = nc.Dataset(path)
                        source_path = path
                    u, v = rotate_uv(source["u_eastward"][index, -1].T,
                                     source["v_northward"][index, -1].T, renderer.grid.angle)
                    renderer.render(u, v, rows, day, date, frame, signature)
                    written += 1
                    status = "written"
                ae, ce = counts(rows)
                writer.writerow(dict(frame=number, day=day, date=f"{date:%Y-%m-%d}",
                                     source_file=str(path), time_index=index, frame_path=str(frame),
                                     AE=ae, CE=ce, status=status))
                handle.flush()
                if (number + 1) % 50 == 0:
                    print(f"Completed {number + 1:,}/{len(selected):,} frames through day {day}", flush=True)
        temporary_manifest.replace(manifest)
    finally:
        if source is not None:
            source.close()
        if renderer is not None:
            renderer.close()
    print(f"Finished {len(selected):,} frames: {written:,} written, {len(selected) - written:,} skipped")
    print(f"Manifest: {manifest}")


if __name__ == "__main__":
    main()
