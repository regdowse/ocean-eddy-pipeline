# AVISO Tasman Sea Eddy Dataset (1994–2019)

This package applies the SEACOFS surface eddy framework to daily AVISO
altimetry. It uses absolute geostrophic velocities (`ugos`, `vgos`) and runs:

1. Nencioli candidate detection.
2. DOPPIO surface fitting.
3. Continuous temporal tracking across all annual files.
4. Quality control and final dataset processing.

There are no subsurface, vertical-profile, or tilt stages.

## Related publications and citation

The published [SEACOFS dataset v1.0.0](https://doi.org/10.5281/zenodo.24486070)
contains model-derived eddies and their vertical structure. It is a separate
product from the AVISO surface workflow in this branch and does not contain
AVISO outputs.

The [Ocean Eddy Pipeline v0.1.1 software archive](https://doi.org/10.5281/zenodo.24457378)
identifies the SEACOFS release; it predates and does not include this AVISO
package. Shared pipeline documentation is in the [repository README](../README.md).
Publish the AVISO outputs as a **separate Zenodo dataset with its own DOI**.
Link that record to the exact producing AVISO commit and a named release tag
from this working branch, and retain the configuration and ESP version/hash.
Shared methods can refer to SEACOFS documentation, but the AVISO inputs, fields,
settings, quality control and limitations need their own concise documentation.
A separate AVISO software DOI is optional if the producing source snapshot is
preserved with the dataset. No AVISO DOI has been assigned in this work.

## Archive scope and provenance

The working branch `aviso/tasman-sea-1994-2019` starts from the preserved
`archive/aviso-tasman-sea-1994-2019` snapshot. That archive contains an older
reference implementation copied from `aviso_eddy_dataset/` in
[`regdowse/UNSW-PhD` at `87f5855cd9c1`](https://github.com/regdowse/UNSW-PhD/tree/87f5855cd9c1a7bfe01d2401fe0d159adfed9f02/aviso_eddy_dataset).
AVISO development remains separate from the SEACOFS `main` workflow.
The original copy includes all tracked AVISO files and a new `config/example.yaml`
derived from the previously ignored local configuration. Snapshot date:
26 November 2026. Generated data and Python/notebook caches are excluded.

The configured input directory contains 26 annual files, `AVISO_0.125_EAC_1994.nc`
through `AVISO_0.125_EAC_2019.nc`. The first and last time coordinates are
**2 January 1994** and **28 February 2019**; these endpoints are partial years.
The native grid spans 145.0625–162.9375°E and 42.9375–25.0625°S.
These dates describe the inputs, not a guarantee of complete retained eddy tracks.

Shared pipeline kernels are included from `ocean-eddy-pipeline` commit
`6bbb22221f344ce851dffc11d39fb7cabb9ff59f`. This is a code snapshot, not a migration
of the original repository's full Git history. That history remains in
`UNSW-PhD` after the working folder is removed.

The original archive's portability changes were limited to `esp_root`, the ESP path,
installation/test/notebook paths for the new layout, and this documentation.
ESP is external: the configured directory should contain the complete
`functions.py` from [ESP v1.1](https://doi.org/10.5281/zenodo.24182671).
Its updated fitting behavior can change results; the archive does not promise
numerical reproduction of the old ESP outputs.

The legacy AVISO dataset is retained at
`/srv/scratch/z5297792/archive_aviso_eddy_dataset`. It was generated using older
ESP functions and is a separate reference product. Generate the new dataset
under `paths.output_root: /srv/scratch/z5297792/aviso_eddy_dataset`; do not copy
legacy partitions into that directory or use the legacy archive as an output root.
The example uses `skip_existing: true` to resume this new calculation.

AVISO and the current SEACOFS configuration both use
`paths.esp_root: /home/z5297792/elliptical_streamfunction_parametrisation`.
Both `doppio` and `out_core_param_fit` were verified to load from that directory's
`functions.py`, with SHA-256
`1c6b574f1084e9ee4eadfd01553464ff6fc5ae514e60180e7e804d09f212da9d`.
Before a production run, verify the loaded function paths again and retain the
actual ESP release identity and file hash with the producing configuration.
Matching the current SEACOFS implementation does not imply numerical
reproduction of the legacy AVISO dataset.

The working configuration now uses **1990-01-01** as `processing.date_origin`,
matching SEACOFS. The archive's former 1950 setting was an error. Source CF time
metadata are decoded to dates before computing this day coordinate: 2 January
1994 is Day 1462 and 28 February 2019 is Day 10650. Regenerate any partitions
made using the old origin into a fresh output root; do not mix day conventions.

Run the AVISO notebooks from `aviso_eddy_dataset/` or its `notebooks/` directory.
Saved outputs are historical. The exploratory `analyse_processed_dataset.ipynb`
additionally imports legacy `seacofs_tilt_tools` and `analysis_tools` from the
original PhD workspace; those analysis helpers are not bundled here and are
not needed by the four-stage AVISO CLI pipeline.

## Archive validation

All seven existing test functions passed when invoked directly with temporary
paths where required (`pytest` was not installed in the available environment).
The example configuration loads, both external ESP functions import from the
configured directory with compatible call signatures, and Python source and
notebook JSON parse successfully. No full dataset run or numerical equivalence
check against old ESP results was performed.

## Grid handling

AVISO longitude and latitude are converted to increasing Cartesian kilometre
axes. The unrotated velocities are treated internally in `(longitude,
latitude)` order.

Only Nencioli uses the configurable 1 km interpolated grid. Every detected
centre is mapped back to the nearest native AVISO grid cell. DOPPIO then uses
native-resolution `ugos`, `vgos`, and native Cartesian coordinates.

## Reused SEACOFS functions

The package imports the established science kernels from the sibling
`seacofs_eddy_dataset` package in this branch: Nencioli detection, DOPPIO geometry
helpers, the ESP function loader, tracking, processing helpers, and atomic
Parquet I/O. All AVISO-specific loading and orchestration remains in this
folder; the shared kernels are retained at the repository root.

## Installation on Katana

From the `ocean-eddy-pipeline` archive checkout root:

```bash
python -m pip install -e .
python -m pip install -e ./aviso_eddy_dataset
```

Copy and edit the example configuration if a machine-specific version is
needed:

```bash
cp aviso_eddy_dataset/config/example.yaml aviso_eddy_dataset/config/local.yaml
```

The committed example already points to:

```text
input:  /srv/scratch/z5502183/AVISO_0.125
output: /srv/scratch/z5297792/aviso_eddy_dataset
ESP:    /home/z5297792/elliptical_streamfunction_parametrisation
```

## Running

List stages:

```bash
aviso-eddy list-stages
```

Run one stage:

```bash
aviso-eddy run-stage detect_nencioli --config aviso_eddy_dataset/config/example.yaml
aviso-eddy run-stage fit_doppio_surface --config aviso_eddy_dataset/config/example.yaml
aviso-eddy run-stage track_eddies --config aviso_eddy_dataset/config/example.yaml
aviso-eddy run-stage process_tracked_dataset --config aviso_eddy_dataset/config/example.yaml
```

Run the complete pipeline:

```bash
aviso-eddy run-all --config aviso_eddy_dataset/config/example.yaml
```

### Batch runs and provenance

Use the AVISO batch runner from the worktree root; the root `run_pipeline.pbs`
belongs to SEACOFS:

```bash
qsub -v EDDY_CONFIG=/absolute/path/config.yaml aviso_eddy_dataset/run_pipeline.pbs
```

The AVISO script activates the worktree `.venv` and initially requests two CPUs,
8 GB RAM and two hours. Set workers within that allocation, and adjust resources
after measuring a pilot. It checks the loaded ESP function paths, call signatures,
input coordinates and continuous daily coverage. All configured paths must be
absolute, and the output root must be separate from inputs and any configured
`validation.legacy_root`. Optional `validation.start_date` and `end_date` enforce
the expected source interval. Missing detection/surface-fit partitions stop the
downstream stages, including when an older consolidated output already exists.

Commit source changes before running. The runner records the producing commit,
configuration, input/ESP SHA-256 hashes, package versions and environment under
`output_root/provenance/`. It retains a source archive and runs each stage in a
fresh process from a private extraction of that archive. Output resumes require
the same producing commit, config, package versions, inputs and ESP file; use a
fresh output root after changes. `execution_status.json` records stage timings
and completion/failure. A completed process is not by itself a scientific audit.

Prepare a small cross-year input subset without altering the source archive:

```bash
python aviso_eddy_dataset/prepare_pilot.py \
  --work-root /srv/scratch/z5297792/aviso_validation/pilot_19941101_19950131 \
  --start-date 1994-11-01 --end-date 1995-01-31
```

This creates separate annual subsets, verifies unchanged coordinate/time/velocity
values after writing, saves original file hashes and source time indices, and
creates a local configuration. For a two-day smoke test use 1994-12-31 through
1995-01-01 and a separate work root. Empty final tracks are expected in that
smoke test because the normal minimum duration is 21 elapsed days.

After the four stages, audit by calendar date against the legacy archive:

```bash
python aviso_eddy_dataset/audit_run.py \
  --config /absolute/path/to/pilot/config.yaml \
  --legacy-root /srv/scratch/z5297792/archive_aviso_eddy_dataset \
  --require-processed
```

Omit `--require-processed` for the two-day smoke test. The audit checks date/day
mapping and keys, compares detection candidates exactly, and compares matched
surface fits using original candidate coordinates/date/cyclonicity. It writes
`validation/comparison.json`, daily counts and matched-fit tables. Legacy Day
labels use 1950 and new labels use 1990; neither raw Day labels nor final Eddy
IDs are correspondence keys. Pilot track lifetimes and edge retention are
truncated, so final population counts cannot be compared as if both runs covered
the full record.

Set `EDDY_LEGACY_ROOT` when submitting to run this audit after the pipeline.
`EDDY_REQUIRE_PROCESSED=1` requires a nonempty pilot population. Optional
`EDDY_PREVIEW_START` and `EDDY_PREVIEW_END` select a short daily-image preview
after a successful audit. The pipeline and audit retain existing scientific
thresholds; they do not tune results to reproduce the legacy population.

For the full record, `EDDY_AUDIT_MODE=summary` selects a lighter automatic audit:
all partition/date/key/track-continuity checks, daily and annual counts, finite
surface-centre counts and broad legacy population totals. It skips individual
candidate matching and does not write a full matched-fit table. The equivalent
standalone option is `audit_run.py --summary-only`. Optional
`validation.expected_files` and `validation.expected_days` check planned coverage.

The full Katana configuration is kept in ignored
`aviso_eddy_dataset/config/local.yaml`, derived from the example. For the
1994–2019 calculation use 16 workers and request one node with 16 CPUs, 32 GB
and a 12-hour walltime, overriding the pilot defaults:

```bash
qsub -l select=1:ncpus=16:mem=32gb -l walltime=12:00:00 \
  -v EDDY_CONFIG=aviso_eddy_dataset/config/local.yaml,EDDY_LEGACY_ROOT=/srv/scratch/z5297792/archive_aviso_eddy_dataset,EDDY_REQUIRE_PROCESSED=1,EDDY_AUDIT_MODE=summary \
  aviso_eddy_dataset/run_pipeline.pbs
```

Submit from the worktree root. PBS owns the job after submission, so disconnecting
does not interrupt it. Check `qstat -u "$USER"`; `output_root/provenance/execution_status.json`
records completed stages while running, and `output_root/validation/summary.json`
records the automatic full-run audit when finished. The requested walltime is an
execution limit, not a runtime estimate. Queue time is additional.

### Initial pilot results (27 November 2026)

Smoke job `9885855` and 92-day pilot job `9885865` both completed with exit
status 0 using producing commit `e2c0f2e`. The pilot covered 1 November 1994–
31 January 1995 and generated all four stages plus three daily overlay frames.

| Pilot comparison | Updated ESP | Legacy reference |
| --- | ---: | ---: |
| Detection candidates | 7,012 | 7,012, identical candidates |
| Finite fitted centres | 6,870 | 6,861 |
| Tracks with at least 21 elapsed days in the pilot window | 95 | 95 |
| Processed eddy-days for those tracks | 4,079 | 4,042 |

The legacy duration reference filters the published full-record tracks to this
date window; it is not a rerun of legacy tracking. Without that duration filter,
the date-window subset includes 124 legacy tracks and 4,343 eddy-days. Raw totals
therefore exaggerate a population difference caused by truncating the record.
The updated pilot contains 46 AE and 49 CE tracks, with 45 tracks crossing the
year boundary. Equal track counts do not imply identical trajectories or IDs.

Across candidates with finite centres in both versions, median centre separation
is 7.7 m and the 95th percentile is 264 m. Thirteen previously missing centres
became finite, while four became missing. Twelve raw candidates changed centre
by more than 10 km; only one reaches the updated processed dataset. Its new
centre is 0.9 km from the initial detection versus 37 km for the rejected legacy
fit, consistent with the existing centre-error filter. Large raw outer-radius
changes also occur among poorly constrained fits; inspect downstream screening
rather than treating every raw fit as an accepted eddy.

The pilot took 2 minutes 30 seconds on two CPUs, using approximately 1.02 GB
peak memory. These are pilot measurements, not a full-record runtime guarantee.
Coverage, rare failures and long-track behaviour still require the full-record
run. No scientific thresholds were adjusted to obtain these pilot results.

Alternatively, use the concise Katana control notebook at
`aviso_eddy_dataset/notebooks/run_pipeline.ipynb` to load configuration, run
individual or selected stages, and inspect detection, tracking, and processing
outputs.

After processing, open
`aviso_eddy_dataset/notebooks/analyse_processed_dataset.ipynb` for a simple
dataset overview, missing-value checks, lifetime and radius distributions,
spatial and temporal coverage, and inspection of an individual eddy track.

Use `aviso_eddy_dataset/notebooks/compare_original_esp_reconstruction.ipynb`
to compare native AVISO `ugos`/`vgos` with the ESP reconstruction for three
AEs and three CEs at early, middle, and late stages of their tracked lives.

Use the standalone [daily snapshot workflow](notebooks/daily_snapshots/README.md)
to render a fixed-layout, resumable sequence of native AVISO velocity overlays:

```bash
python aviso_eddy_dataset/notebooks/daily_snapshots/render_frames.py \
  --config aviso_eddy_dataset/config/local.yaml \
  --start-date 1996-09-02 --end-date 1996-09-04
```

It writes PNGs, provenance settings and a chronological CSV manifest under
`output_root/daily_overlay_frames/`. A tracked PBS runner is included in the same
folder and uses the worktree's `.venv`. The historical overlay notebook is kept
as a reference; the standalone script provides date/day consistency checks,
fixed layout and signature-verified resumes.

Detection and surface fitting write one resumable Parquet partition per annual
source file. Tracking reads every partition together, sorts by the continuous
day coordinate, and therefore tracks across year boundaries.

## Outputs

```text
/srv/scratch/z5297792/aviso_eddy_dataset/
  detections/source=AVISO_0.125_EAC_1994.parquet
  surface_eddies/source=AVISO_0.125_EAC_1994.parquet
  tracked/eddy_tracks.parquet
  processed/eddy_dataset_processed.parquet
```

Set `parallel.skip_existing: true` to resume the expensive file-level stages.
Set it to `false` when parameters change and partitions must be regenerated.
