# Ocean Eddy Pipeline

This repository contains the SEACOFS application of a modular ocean eddy
pipeline: Nencioli surface detection, DOPPIO fitting, temporal tracking,
vertical profile extraction, and tilt analysis. This first release preserves
the existing scientific implementation as a fixed version for citation.
Support for other models is outside this release's scope.

The Python distribution is `seacofs-eddy-dataset` version `0.1.0`; imports use
`seacofs_eddy_dataset`. Model inputs and generated datasets are not included.

## Installation

Use Python 3.10 or later in your chosen environment. From the repository root:

```bash
cd /path/to/ocean-eddy-pipeline
python -m pip install -e .
seacofs-eddy list-stages
```

Use the Python executable for that environment (`python3` where appropriate).
Dependencies are declared in `pyproject.toml`. To use the runner notebook,
install Jupyter separately and select the same Python environment as its kernel.
ESP must also be installed separately for the DOPPIO stages below.

## SEACOFS configuration and inputs

Edit the supplied, tracked `config/local.yaml`. Its Katana paths document the
original SEACOFS application; change them for another installation. Paths are
used as supplied, so absolute paths are recommended. Run commands from the
repository root when using the relative config path below.

Required inputs and assumptions in the current implementation:

- `paths.model_root`: directory containing `outer_avg_*.nc` files. The final
  underscore-separated filename component must be an integer `fnumber`.
- `files.grid_reference`: reference file under `model_root`, supplied as
  `outer_avg_01461.nc`. It must contain `lon_rho`, `lat_rho`, and `angle`;
  `mask_rho` and `h` are read if present. Grid arrays are transposed into
  `(x, y)` order. Cartesian distances are in kilometres, constructed from
  cumulative distances along the middle grid row and column. Velocity rotation
  uses the single reference angle at `[0, 0]`.
- Model files must contain `ocean_time`, `u_eastward`, and `v_northward`.
  Velocity is indexed as `(time, depth, y, x)`, with the final depth index
  used for the surface. For vertical interpolation the depth order is reversed
  after transposition to `(x, y, depth)`. The existing rotation is applied
  despite the velocity variable names; input conventions must match SEACOFS.
- `ocean_time` is divided by 86400 to obtain days; processing assigns dates
  using the configured `1990-01-01` origin. The code does not derive this origin
  from NetCDF time metadata. Processing also retains the SEACOFS filename/day
  mapping (`file_start_fnumber: 1461`, `file_stride_days: 30`,
  `file_day_offset: 1462`).
- `paths.z_r`: local NumPy `.npy` depth array aligned with the transposed and
  depth-reversed velocity fields, in `(x, y, depth)` order and metres.
  Interpolation uses absolute depths. Default target depths come from
  `abs(z_r[150, 150, 1:])`, requiring those horizontal indices to exist.
  Surface fitting also needs this array with the supplied vertical acceptance
  check enabled (`require_vertical_profile: true`, minimum depth 50 m).
- `paths.output_root`: writable parent directory for all generated outputs.
- `paths.esp_root`: external ESP directory containing `functions.py`, as
  described below.

The supplied config uses 16 process workers and `parallel.skip_existing: false`.
Rerunning stages therefore replaces their outputs. Set `skip_existing: true`
for stages that support resuming by output existence. This check does not
validate whether existing outputs match changed inputs or settings. Vertical
profile QC and analysis regenerate their consolidated outputs regardless of
that setting. Reload the config in a notebook after editing it.

## External ESP dependency

DOPPIO surface fitting and vertical profile extraction require Elliptical
Streamfunction Parametrisation (ESP) **v1.01**, the version used for this
SEACOFS application.

1. Download and extract ESP v1.01 from its
   [version-specific Zenodo record](https://zenodo.org/records/19364198)
   ([source release](https://github.com/regdowse/elliptical_streamfunction_parametrisation/tree/v1.01)).
2. Set `paths.esp_root` in `config/local.yaml` to the extracted local
   directory containing `functions.py`. The supplied
   `/home/z5297792/elliptical_streamfunction_parametrisation` is specific to
   the Katana installation.
3. Provide the dependencies required by that ESP release in the same Python
   environment, following its own installation instructions.

The adapter adds this directory to `sys.path`, imports the module `functions`,
and calls `functions.doppio` and `functions.out_core_param_fit`. ESP is external
and is not installed by this package. Cite it separately using its version DOI:
[10.5281/zenodo.19364198](https://doi.org/10.5281/zenodo.19364198).

## Running the pipeline

The stages run in this order:

| Stage | Output or purpose |
| --- | --- |
| `detect_nencioli` | Surface candidates, partitioned by model file |
| `fit_doppio_surface` | DOPPIO surface fits, partitioned by model file |
| `track_eddies` | Quality control and temporal linking |
| `process_tracked_dataset` | Cleaned tracks and model-file/date mapping |
| `compute_vertical_profiles` | Profiles, partitioned by model file |
| `qc_vertical_profiles` | Confirmed profiles |
| `compute_tilt` | Delta tilt estimates |
| `analyse_tilt` | Summary tables |

Run individual stages after their upstream outputs exist, or run the sequence:

```bash
seacofs-eddy run-stage detect_nencioli --config config/local.yaml
seacofs-eddy run-stage fit_doppio_surface --config config/local.yaml
seacofs-eddy run-all --config config/local.yaml
```

The equivalent module entry point is:

```bash
python -m seacofs_eddy_dataset.cli list-stages
python -m seacofs_eddy_dataset.cli run-stage detect_nencioli --config config/local.yaml
```

`notebooks/run_pipeline.ipynb` is the supported notebook control panel. Open it
from the repository root or the `notebooks` directory, review the config, and
select stages in `STAGES_TO_RUN` before executing that cell. Its supplied list
selects only `compute_tilt` and `analyse_tilt`, requiring existing confirmed
profiles. The `run_all(config)` shortcut is commented out. Other exploratory
notebooks and helpers are excluded from this release.

## Outputs and resuming

Detection, surface fitting, and profile extraction process model files in
parallel using `parallel.workers` and `parallel.backend`. Each writes one
Parquet partition per input file. Other stages write consolidated tables.

```text
output_root/
  detections/
    fnumber=01461.parquet
  surface_eddies/
    fnumber=01461.parquet
  tracked/
    eddy_tracks.parquet
  processed/
    eddy_dataset_processed.parquet
  vertical_profiles/
    fnumber=01461.parquet
  vertical_profiles_confirmed/
    profiles.parquet
  tilt/
    tilt_dataset.parquet
  analysis/
    tilt_summary.parquet
    profile_tilt_summaries.parquet
```

`analyse_tilt` writes summary tables; it currently does not generate figures.
Partition writes use a temporary file followed by replacement. With
`skip_existing: true`, existing outputs are skipped by detection, surface
fitting, tracking, processing, profile extraction, and tilt computation.

### Delta Tilt Settings

The production delta method uses `tilt.smoothing_days: 5` and
`tilt.temporal_sigma_days: 1.0`: calendar days k-2 through k+2, with Gaussian
weights of approximately 5.45%, 24.42%, 40.26%, 24.42%, and 5.45%.
Temporal weights apply to mean depth increments and renormalize at each depth
over available values. Depth-fit weights still use unweighted sample variance
over the five-day window. The first and last two calendar days are excluded;
only intervals with finite x/y increments on the reference day are used.
This restriction is applied before temporal averaging, variance estimation,
and cumulative reconstruction. Neighbours cannot extend the reference depth
range, and missing reference days receive missing tilt values. A 0-200 m
profile supplies fit labels 0-190 m and fails the unchanged 200 m minimum span.
Depth limits, line fitting, and the deep-to-shallow bearing are unchanged.

To regenerate existing results, set `parallel.skip_existing: false`, reload
the configuration, and rerun `compute_tilt` followed by `analyse_tilt`.
This overwrites `tilt/tilt_dataset.parquet`; vertical profiles need not be rerun.
Refresh downstream analysis tables that cache tilt values after regeneration.
For seven-day equal temporal weighting, use `smoothing_days: 6` and
`temporal_sigma_days: null` (legacy even window values select one extra day).
The reference-day depth restriction applies to every temporal weighting choice.
`analyse_tilt` summarises the regenerated Delta estimates, excluding missing
estimates from its means and medians. Its separate `profile_tilt_summaries`
table remains a raw per-day displacement diagnostic, not a Delta fit.

## Code organisation

Scientific kernels live in `src/seacofs_eddy_dataset/core/`. Stage modules in
`src/seacofs_eddy_dataset/stages/` orchestrate I/O and execution. The runner
notebook provides configuration, stage selection, and output inspection.

## Citation and licensing

The author is Reg Dowse. Citation metadata is provided in `CITATION.cff`.
This repository is available under the [MIT licence](LICENSE). A pipeline DOI
has not yet been assigned. ESP remains a separate dependency under its own
licence; cite ESP separately as described above.

This release preparation changes documentation and notebook saved outputs only;
scientific source, configuration values, and notebook code are preserved.
Static file checks passed, but installation and CLI execution still need
verification in a Python >=3.10 environment with the required dependencies.
