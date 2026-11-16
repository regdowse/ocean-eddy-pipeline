# Changelog

## 0.1.1

This release updates the SEACOFS pipeline to use external ESP v1.1
([Zenodo DOI](https://doi.org/10.5281/zenodo.24182671)), replacing ESP v1.01.
The updated dependency can change fitted parameters and downstream results.

- Rename the external ESP configuration key from `paths.esp_zonodo` to
  `paths.esp_root`. Existing configuration files must use the new key.
- Set the supplied Katana ESP path to
  `/home/z5297792/elliptical_streamfunction_parametrisation`.
- Update package version, citation metadata, and runner notebook instructions.
- Add a PBS batch script for all stages, with a configurable virtual environment
  and submission directory as its working directory; ignore PBS job logs.
- Document the local v0.1.0 results archive and the fresh output directory for
  the next run. These local data directories are outside the software release.

The v0.1.1 dataset has not yet been generated. Required ESP function definitions
and argument signatures were checked in the local source. Full numerical
compatibility and pipeline execution remain to be verified in the target
environment; the available Python 3.12 environment lacks PyYAML.
