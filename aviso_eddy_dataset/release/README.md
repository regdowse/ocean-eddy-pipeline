# AVISO-derived mesoscale eddy dataset for the East Australian Current and Tasman Sea (1994–2019)

**Version:** 1.0.0. **Creator:** Reg W. Dowse.  
**Dataset and preserved-source DOI:** https://doi.org/10.5281/zenodo.24575702  
**Derived eddy tables and documentation:** CC BY 4.0. **Pipeline source:** MIT.

Generated using E.U. Copernicus Marine Service Information;
https://doi.org/10.48670/moi-00148.

This release contains surface eddy detections, fitted parameters and tracks
derived from daily absolute geostrophic velocities (`ugos`, `vgos`) in regional
AVISO/SSALTO-DUACS altimetry files. Input coverage is **2 January 1994–28 February
2019**, inclusive: 9,189 days in 26 annual files, with partial endpoint years.
The processed dataset contains **9,002 eddies** (4,114 anticyclonic, 4,888
cyclonic) and **454,519 eddy-days**. These are velocity-defined fitted features;
they are not an official AVISO eddy catalogue or direct measurements of eddy
boundaries. There are no subsurface profiles or tilt estimates.

## Start here

```python
import pandas as pd
surface = pd.read_parquet('processed/eddy_dataset_processed.parquet')
track = surface.loc[surface.Eddy.eq(1)].sort_values('Day')
```

| Path | Contents | Rows |
| --- | --- | ---: |
| `processed/eddy_dataset_processed.parquet` | Final surface tracks; start here | 454,519 |
| `tracked/eddy_tracks.parquet` | Accepted, linked observations before final filtering | 707,115 |
| `detections/` | 26 annual candidate partitions | 742,803 |
| `surface_eddies/` | 26 annual fit-attempt partitions, including missing fits | 742,803 |
| `variables.csv` | Field definitions, units and stage-specific meanings | — |
| `static_grid.nc` | Native geographic coordinates, Cartesian axes and source-index mapping | — |
| `generation_config.yaml` | Exact producing configuration, including historical absolute paths | — |
| `requirements-generation.txt` | Recorded package pins, excluding local editable installation paths | — |
| `provenance/` | Producing source archive, hashes, original environment and stage status | — |
| `validation/` | Full-run coverage/key checks and daily/annual population counts | — |
| `release_manifest.json`, `checksums.sha256` | Release inventory and file identities | — |

Annual partitions are named `source=AVISO_0.125_EAC_YYYY.parquet`. Partition
names identify source files, not individual eddies or independent yearly
tracking runs. The archived source is `provenance/source.tar`; it is the exact
producing checkout, including shared SEACOFS kernels and the AVISO package.
Original velocity files, ESP itself, legacy AVISO outputs, images and movies
are not included. Velocities are needed to rerun extraction and draw background
currents, but not to read these tables. ESP is an external dependency.

## Dates, identifiers and coordinates

- `Day` is an integer number of days since **1990-01-01**. It spans 1462–10650.
  `Date` is the corresponding daily timestamp. Legacy AVISO products used a
  different day origin; join different products by calendar date, not raw Day.
- `(Eddy, Day)` uniquely identifies a final eddy-day. Final `Eddy` IDs are
  renumbered after filtering and do not preserve tracked-stage IDs. Detection
  and surface-fit tables have no final track ID. `eddy_idx` is within-day only.
- `Age` is the total number of processed daily rows in a track, repeated on
  every row, **not its elapsed age on that date**. Retained tracks span at least
  21 elapsed days (at least 22 daily rows); observed Age ranges from 22 to 530.
- Horizontal fit positions and radii use kilometres. The Cartesian origin is
  the southwest native grid point; axes increase eastward and northward.
  Longitudes/latitudes use signed degrees east/north. Native grid coverage is
  145.0625–162.9375°E and 42.9375–25.0625°S, at 0.125° spacing.
- Cartesian axes are cumulative spherical distances along mean latitude and
  longitude, with the implementation's 6,357 km Earth radius. They are an
  approximate regional coordinate system, not a standard map projection.
  `static_grid.nc` preserves those axes and sorted geographic coordinates.
- `ic`, `jc`, `nic`, `njc` are zero-based indices in increasing-coordinate
  `(longitude, latitude)` order. Use the supplied source-index arrays when
  accessing the original source-file ordering. AVISO velocities are unrotated.
- `source_file` preserves a machine-local absolute path. Its basename identifies
  the annual input; the original path is not expected to exist on another system.

## Method and screening

Nencioli vector-geometry detection uses velocities linearly interpolated to a
1 km grid, with windows `a=4`, `b=3`. Candidates are mapped to the nearest
native AVISO cells. DOPPIO fitting uses native-resolution velocity transects
extending 30 km either side of the candidate, not the interpolated grid.

The elliptical coordinate is `rho² = rᵀ Q r`, where Q is a symmetric,
dimensionless shape matrix. The aspect ratio is `sqrt(lambda_max/lambda_min)`.
`R` is the mean available four-direction peak-speed radius. Outer Gaussian
fitting uses `rho <= max(min(1.75*R, 200), 30)` km and a rectangular extraction
half-width three times that limit. `Rc` is the fitted Gaussian scale, distinct
from R. Displayed ellipses in the supplied code use `rho² = Rc²/2`.

Surface attempts retain missing parameters after failure. Of 742,803 attempts,
725,468 have finite fitted centres. Tracking acceptance requires consistent
detection/fitted cyclonicity, a centre inside the grid, finite nonzero
`abs(Omega0) <= 5e-5 s^-1`, and acceptable centre error. The error ceiling is
`expm1(median(log1p(error)) + 4*MAD(log1p(error))/0.6745)`; zero MAD supplies no
upper ceiling. This statistic is calculated across the fitted population.

Tracking runs continuously across annual boundaries, matching like cyclonicity
within unit distance in `(x/50, y/50, Omega0/1e-5)`. It searches the nearest
preceding calendar day first, up to four days back. Each previous track may be
claimed once per current day. This is sequential candidate assignment.

Processing applies a centred three-observation mean to Q, removes tracks
spanning fewer than 21 elapsed days, and invalidates shape/fit parameters at
aspect ratio >5. Outer fits with Rc>300 km, Rc>1.75R, abs(Omega)>5e-5 s^-1 or
abs(psi0)>300 stored units fall back to Omega0 and lose Rc/psi0. Missing days
are inserted and parameters interpolated, with endpoint filling and no configured
maximum outer-parameter gap. Tracks with an entirely missing required parameter
or mean R<=15 km are removed. The radius threshold applies to the track mean,
not every daily row. Final Q/aspect ratio and geographic coordinates are updated;
processed `w = Omega*(q11+q22)`.

The final table has no missing values. **That does not imply every parameter
was independently fitted on every day**: values can be smoothed or interpolated.
There is no per-variable observed/interpolated flag. Treat intermediate fit
failures as missing values, not zeros. Track IDs can change after regeneration.

## Units and interpretation

`Omega0`, `Omega` and `w` are stored in s^-1 after the factor-0.001 conversion
from fits using km coordinates and m/s velocity. `w` denotes **relative
vorticity**, not vertical water velocity. Southern Hemisphere AE vorticity is
positive and CE vorticity negative. `psi0` retains the implementation's mixed
units **m km s^-1**; multiply by 1,000 for m²/s. See `variables.csv` for details.
Feature sizes and fitted geometry depend on altimetric resolution, regional
boundaries, geostrophic assumptions and screening/interpolation choices. The
release does not provide uncertainty estimates for individual fits.

## Producing code, dependency and validation

The data were produced by commit
[`32e769460fb34284df7ab8d1972d52df2f524dd0`](https://github.com/regdowse/ocean-eddy-pipeline/tree/32e769460fb34284df7ab8d1972d52df2f524dd0).
The documentation release is tagged
[`aviso-dataset-v1.0.0`](https://github.com/regdowse/ocean-eddy-pipeline/tree/aviso-dataset-v1.0.0).
These identities differ because publication documentation was finalised after
the run; the release builder verifies that both scientific source trees match
the producing archive. Historical citation metadata inside `source.tar` is
preserved unchanged. Use this release's root `CITATION.cff` for the AVISO data
and accompanying source, rather than that historical SEACOFS citation file.

The imported ESP `functions.py` SHA-256 was
`1c6b574f1084e9ee4eadfd01553464ff6fc5ae514e60180e7e804d09f212da9d`.
It matches the archived [ESP v1.1 computational implementation](https://doi.org/10.5281/zenodo.24182671),
which is also byte-identical to v1.2's computational file. The local dependency
was not a versioned Git checkout, so this file hash is the precise run identity;
the release label alone does not distinguish those identical files.

Python was 3.10.8; package versions and the original environment export are
retained. To reproduce, extract `provenance/source.tar`, create a Python 3.10
environment, install the package pins, install both packages from that extracted
checkout (`pip install -e . -e ./aviso_eddy_dataset`), obtain the matching external
ESP release, and adjust input/output/ESP paths in a copy of the configuration.
The original input file hashes identify the source snapshot actually used.

PBS job 9885962 completed with exit status 0 on 27 November 2026. The audit
verified all 26 detection and fitting partitions, 9,189 continuous source dates,
date/day mapping, unique eddy-day keys, processed track continuity and broad
legacy counts. A detailed 92-day pilot compared matched candidates and inspected
real overlay frames. The full-run audit is not a fit-by-fit equivalence test.
Legacy results contained 8,979 eddies and 453,309 eddy-days and used older ESP
functions and a 1950 day origin. They are separate from this release.

## Attribution and citation

Cite this combined data-and-preserved-source release as:

> Dowse, R. W. (2026). AVISO-derived mesoscale eddy dataset for the East Australian
> Current and Tasman Sea (1994–2019) (Version 1.0.0) [Data set]. Zenodo.
> https://doi.org/10.5281/zenodo.24575702

Also acknowledge the source product and scientific methods as appropriate:

- [Global Ocean Gridded L4 Sea Surface Heights and Derived Variables Reprocessed](https://doi.org/10.48670/moi-00148),
  Copernicus Marine product `SEALEVEL_GLO_PHY_L4_MY_008_047`. The local inputs
  retain `product_version=vNov2024` and `software_version=8.0_MIOST_DT2024_baseline`.
  The precise download command/dataset ID was not retained; the parent product
  is identified from native metadata and its documented distribution.
- [ESP method](https://doi.org/10.5194/egusphere-2026-3599) and
  [matching archived ESP implementation](https://doi.org/10.5281/zenodo.24182671).
- [Nencioli et al. (2010)](https://doi.org/10.1175/2009JTECHO725.1).
- [Shared SEACOFS pipeline software](https://doi.org/10.5281/zenodo.24457378).
  This software DOI predates the AVISO implementation. The separate
  [SEACOFS dataset](https://doi.org/10.5281/zenodo.24486070) contains model-derived
  eddies and is not this observationally derived surface product.

Read `LICENSE-data.txt` and `LICENSE-code.txt` for component-specific terms.
Copernicus Marine acknowledgement guidance is at
https://help.marine.copernicus.eu/en/articles/4444611-citing-copernicus-marine-products-and-services.
