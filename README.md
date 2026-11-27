# Ocean Eddy Pipeline: AVISO application

[![AVISO dataset DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.24575702.svg)](https://doi.org/10.5281/zenodo.24575702)

This branch contains the AVISO surface application of Ocean Eddy Pipeline:
Nencioli detection, native-grid DOPPIO/ESP fitting, continuous tracking and
processed surface eddy tables. There are no vertical-profile or tilt stages.

**Data and preserved producing source:**
[10.5281/zenodo.24575702](https://doi.org/10.5281/zenodo.24575702), dataset version
**1.0.0**. The release contains **9,002 eddies and 454,519 eddy-days**, derived
from daily absolute geostrophic AVISO/SSALTO-DUACS velocities covering
**2 January 1994–28 February 2019** in the East Australian Current/Tasman Sea region.
Generated using E.U. Copernicus Marine Service Information;
https://doi.org/10.48670/moi-00148.

## Start here

- [AVISO installation, configuration, methods and run instructions](aviso_eddy_dataset/README.md).
- [Dataset README and usage](aviso_eddy_dataset/release/README.md).
- [Variable dictionary](aviso_eddy_dataset/release/variables.csv).
- [Daily snapshot renderer and PBS runner](aviso_eddy_dataset/notebooks/daily_snapshots/README.md).

Use Python 3.10 or later and a separate environment. From this checkout:

```bash
python -m pip install -e . -e ./aviso_eddy_dataset
aviso-eddy list-stages
```

The root `seacofs_eddy_dataset` package supplies shared scientific kernels;
`aviso_eddy_dataset` supplies AVISO-specific loading and orchestration. Original
velocity files and external ESP are required for regeneration. Large generated
datasets are distributed through Zenodo, rather than Git.

## Citation and provenance

Cite the single dataset DOI above for the released AVISO data and preserved
source. `CITATION.cff` provides dataset citation metadata. The actual producing
commit is
[`32e769460fb34284df7ab8d1972d52df2f524dd0`](https://github.com/regdowse/ocean-eddy-pipeline/tree/32e769460fb34284df7ab8d1972d52df2f524dd0).
The documentation release is tagged
[`aviso-dataset-v1.0.0`](https://github.com/regdowse/ocean-eddy-pipeline/tree/aviso-dataset-v1.0.0).
The deposit preserves the exact producing archive and its configuration,
ESP/input hashes, environment and validation results. The AVISO Python component
version is 0.1.0; dataset and software component versions are independent.

The derived eddy tables/documentation use CC BY 4.0. Pipeline code retains the
[MIT licence](LICENSE); native source-coordinate components retain Copernicus
Marine terms. See the [component licence notice](aviso_eddy_dataset/release/LICENSE-data.txt).
Cite the source product, ESP implementation and scientific methods as described
in the dataset README.

## Related SEACOFS publications

The maintained [SEACOFS application on main](https://github.com/regdowse/ocean-eddy-pipeline/tree/main)
and its [v0.1.1 software archive](https://doi.org/10.5281/zenodo.24457378) are
separate resources. The [SEACOFS eddy dataset](https://doi.org/10.5281/zenodo.24486070)
contains model-derived eddies and vertical structure. Its software DOI predates
this AVISO implementation. Shared SEACOFS instructions are available at the
[versioned SEACOFS README](https://github.com/regdowse/ocean-eddy-pipeline/blob/v0.1.1/README.md).
The older AVISO starting snapshot remains on
`archive/aviso-tasman-sea-1994-2019`; work continues on
`aviso/tasman-sea-1994-2019`.
