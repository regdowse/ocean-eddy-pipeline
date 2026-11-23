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
- Document the local v0.1.0 results archive and the completed ESP v1.1 run;
  clarify that local inputs and generated datasets are outside the software release.
- Distinguish the existing v0.1.0 Zenodo DOI from the pending v0.1.1 archive.

PBS job `9801291` reported completion on 17 November 2026 with exit status 0,
listing products through tilt analysis and confirming the intended ESP import
paths. See the README for execution evidence and memory-use qualifications.
This is not a numerical-equivalence test against ESP v1.01.
