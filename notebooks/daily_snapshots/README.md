# Daily SEACOFS snapshots

`render_frames.py` reproduces the styling of the archived
`generate_daily_overlay_frames.ipynb`: `Blues_r` surface speed, grey velocity
arrows, red anticyclonic and cyan cyclonic eddies, outlined white IDs, geographic
contours, and the date/day/population title. It reads existing products and
does not run any dataset-generation stages.

## Setup and inputs

From the repository root, in Python >=3.10:

```bash
python -m pip install -e '.[plotting]'
python notebooks/daily_snapshots/render_frames.py --help
```

Review `config/local.yaml`: the script needs `paths.model_root`,
`files.grid_reference`, `files.model_pattern`, `paths.output_root`, and
`processing.date_origin`. The processed surface table defaults to
`output_root/processed/eddy_dataset_processed.parquet`.

The released eddy tables are available in the
[SEACOFS dataset v1.0.0](https://doi.org/10.5281/zenodo.24486070).
The producing [pipeline software v0.1.1](https://doi.org/10.5281/zenodo.24457378)
is archived separately; see the [repository README](../../README.md) for citation
guidance.

The original SEACOFS NetCDF velocity files are required for the speed field
and arrows; the published eddy dataset alone cannot reproduce the overlays.
ESP and the vertical depth array are not required. This script preserves the
pipeline's SEACOFS surface index, coordinate grid, rotation and time conventions.

## Render frames

```bash
# Preview a short inclusive range.
python notebooks/daily_snapshots/render_frames.py --start-day 2436 --end-day 2438

# Dates are an alternative to model days.
python notebooks/daily_snapshots/render_frames.py \
  --start-date 1996-09-02 --end-date 1996-09-04

# Render all available model days (including days with no processed eddies).
python notebooks/daily_snapshots/render_frames.py
```

The output defaults to `output_root/daily_overlay_frames/`, outside the source
repository. Override it with `--output-dir /absolute/path`. To compare an older
population, supply `--processed-path /path/to/older/eddy_dataset_processed.parquet`
and a separate output directory. Existing settings must match when resuming;
`--overwrite` redraws selected frames after intentional input or style changes.

Each image is `frame_day_02437.png`, independent of the selected range. The
CSV manifest lists frames chronologically, with dates, source files, time
indices, population counts and written/skipped status. It describes the most
recent successfully completed invocation. Images outside that invocation's
range are retained, so use the manifest to select animation inputs rather than
assuming every PNG in the directory belongs to the current selection.
An interrupted run retains its temporary partial manifest; rerun the same
command to finish it. Do not run simultaneous writers into the same directory.

Images are written atomically. `render_settings.json` records the inputs,
configuration and renderer hashes, Matplotlib version and visual controls.
Individual PNGs carry a signature covering those settings and their source
file's path, size, modification time, day and time index. Resume checks signatures,
pixel dimensions and PNG integrity before skipping existing frames. File identity
checks use size and modification time rather than hashing large model files.

## Appearance and efficiency

Defaults match the notebook's 9 by 10 inch figure at 150 dpi (1350 by 1500 px),
speed range 0–1.377 m/s, arrow spacing 12 grid cells, and existing marker/line
styles. The colourbar reads `Current speed (ms$^{-1}$)`. Use `--dpi`,
`--speed-vmax`, `--quiver-step`, `--quiver-scale`, `--no-labels`, or `--no-quiver`
to adjust these deliberately. The fixed arrow scale defaults to 13.2, close to
the old automatic scale on days 2436–2437; it stays constant throughout a movie.

The original constrained layout is solved once and frozen. Both ellipse lines
and IDs are clipped at the rectangular model extent, preventing edge labels
from moving the map. Limits, aspect, colourbar, colour range and output size
stay fixed. Land masking and geographic contours retain the notebook behaviour.

The renderer reuses static artists and updates speed, arrows, centres, ellipse
lines, labels and title. Ellipse vertices are calculated directly from the
positive-definite fitted matrix, using the same `rho² = Rc²/2` boundary as the
notebook. This avoids contouring the entire grid for every eddy; invalid fits
are omitted. Small subpixel differences from the old grid-contoured outlines
are expected. The script indexes file time metadata first, then opens each
needed velocity file once during rendering and reads only selected surface
slices. It runs headlessly and uses one process with bounded velocity memory.

## Run all days on Katana

From a login node, submit the supplied PBS script **from the repository root**:

```bash
cd /home/z5297792/ocean-eddy-pipeline
qsub notebooks/daily_snapshots/render_frames.pbs
```

It requests one CPU, 4 GB RAM and four hours, activates `${HOME}/myenv310`,
and renders all available model days using `config/local.yaml`. The current
configuration writes PNGs and the manifest to:

```text
/srv/scratch/z5297792/SEACOFS_26yr_eddy_dataset_modular/daily_overlay_frames/
```

No movie is generated. The script does not use `parallel.workers` and limits
numerical-library threads to one. A job-local writable Matplotlib cache is
removed automatically when the shell exits normally.

`qsub` returns the job ID. You can disconnect after submission; check progress
with `qstat -u "$USER"`. Combined output/errors are returned to
`seacofs_frames.o<job-number>` in the submission directory (ignored by Git).
PBS may spool the log until completion. Successful completion ends with the
renderer’s frame counts and manifest path; check the PBS exit status as well.

If interrupted or timed out, submit the same command again to resume. These
resource requests are initial allowances; use the first job's resource report
to adjust subsequent requests if necessary. Do not submit a second writer
while the first is still running.

To use another environment, configuration or output directory:

```bash
qsub -v EDDY_VENV=/absolute/path/to/venv,EDDY_CONFIG=/absolute/path/config.yaml,EDDY_FRAME_DIR=/absolute/path/frames \
  notebooks/daily_snapshots/render_frames.pbs
```

The PBS script deliberately omits `--overwrite`; for an intentional full
redraw, use a new output directory or run the Python command with that option.
