# Daily AVISO snapshots

Render existing processed AVISO eddies over native absolute geostrophic
velocities (`ugos`, `vgos`). This is the AVISO counterpart of
[`notebooks/daily_snapshots/`](../../../notebooks/daily_snapshots/README.md)
for SEACOFS. It reads the AVISO configuration and native coordinate grid and
applies no SEACOFS velocity rotation, depth indexing or model-file/day mapping.
It does not generate or change eddy tables.

## Setup and inputs

From the AVISO worktree root:

```bash
cd /home/z5297792/ocean-eddy-aviso
source .venv/bin/activate
python -m pip install -e . -e ./aviso_eddy_dataset
python aviso_eddy_dataset/notebooks/daily_snapshots/render_frames.py --help
```

The default configuration is `aviso_eddy_dataset/config/example.yaml`. Supply
`--config aviso_eddy_dataset/config/local.yaml` for a machine-specific or fresh
production run. The renderer needs the annual source NetCDF files under
`paths.data_root` and the processed table under
`paths.output_root/processed/eddy_dataset_processed.parquet`. Use
`--processed-path` to select another table, and `--output-dir` to override the
default `paths.output_root/daily_overlay_frames/` destination.

The source files are required for current speed and arrows; the eddy table alone
is insufficient. ESP is not imported or needed by the renderer. Coordinate grids
must match across source files; duplicate daily timestamps are rejected before
any image writes. Missing source days are reported and are not invented.

The table must have unique `(Eddy, Day)` keys and `Date` must equal
`processing.date_origin + Day`. AVISO uses **1990-01-01**, matching SEACOFS;
the former 1950 example setting was an error. Regenerate any tables produced
with that old setting into a fresh output root. A mismatch raises an error
rather than plotting eddies against the wrong day. Frame day numbers follow
the generation configuration.

## Preview and run

```bash
# A short inclusive date range, once the processed table exists.
python aviso_eddy_dataset/notebooks/daily_snapshots/render_frames.py \
  --config aviso_eddy_dataset/config/local.yaml \
  --start-date 1996-09-02 --end-date 1996-09-04

# All available source days, including days without retained eddies.
python aviso_eddy_dataset/notebooks/daily_snapshots/render_frames.py \
  --config aviso_eddy_dataset/config/local.yaml
```

`--start-day` and `--end-day` can be used instead of the corresponding dates.
Run a short preview first and inspect the images before rendering the full
record. A new production calculation should use a fresh output root, separate
from historical results.

## Appearance and resuming

The renderer preserves the established AVISO notebook styling: `Blues_r` speed,
grey arrows, red AE and cyan CE centres/ellipses, outlined white track IDs, and
geographic contours on kilometre axes. The figure is 9 by 10 inches at 150 dpi
(1350 by 1500 pixels). The fixed speed range is 0–1.037 m/s and arrows use every
third native cell. `--speed-vmax`, `--dpi`, `--quiver-step`, `--quiver-scale`,
`--no-labels` and `--no-quiver` control the display. The fixed arrow scale defaults
to 13.2; unlike the historical notebook's automatic arrow scaling, it is constant
across days. Ellipses use the same `rho² = Rc²/2` level as the notebook, drawn
analytically from positive-definite Q matrices. Invalid ellipses are omitted.

The layout, map limits, colour range and arrow scale remain fixed across frames.
Labels and ellipses are clipped to the map. Writes are atomic. PNG metadata
records a signature of renderer/helper/configuration hashes, processed/reference
file identities, source-file identity, date index and display settings. File
identity uses path, size and modification time, rather than hashing large inputs.
Existing frames are skipped only after checking their signature, dimensions and
PNG integrity. Use a new output directory or `--overwrite` after intentional
changes. Do not run simultaneous writers into the same directory.

`render_settings.json` records run settings. `frame_manifest.csv` lists the
selected frames chronologically, with dates, source paths/time indices, AE/CE
counts and written/skipped status. It describes the last successfully completed
invocation, not every PNG that may remain in the directory. An interrupted run
retains a partial `.csv.tmp` manifest; rerun the same command to finish.
No movie is generated.

## Katana batch runner

Submit from the worktree root after generating and checking the processed table:

```bash
qsub -v EDDY_CONFIG=aviso_eddy_dataset/config/local.yaml \
  aviso_eddy_dataset/notebooks/daily_snapshots/render_frames.pbs
```

The runner activates the worktree's `.venv`, requests one CPU, 4 GB RAM and four
hours, limits numerical-library threads, and uses a temporary writable Matplotlib
cache. These resource requests are initial allowances; adjust them using the
first job's resource report. It renders all source days and resumes verified
frames. Logs appear as `aviso_frames.o<job-number>` in the submission directory.
Use `qstat -u "$USER"` to check progress and inspect the PBS exit status.

To override the environment or frame destination:

```bash
qsub -v EDDY_VENV=/absolute/path/to/venv,EDDY_CONFIG=/absolute/path/config.yaml,EDDY_FRAME_DIR=/absolute/path/frames \
  aviso_eddy_dataset/notebooks/daily_snapshots/render_frames.pbs
```

## Publication

The AVISO data will have a separate dataset record and DOI when published. The
[SEACOFS data DOI](https://doi.org/10.5281/zenodo.24486070) contains model-derived
eddies, and the [SEACOFS software DOI](https://doi.org/10.5281/zenodo.24457378)
predates this AVISO package. Neither identifies the AVISO outputs or renderer.
Archive the producing AVISO configuration, commit and release tag with the data.
