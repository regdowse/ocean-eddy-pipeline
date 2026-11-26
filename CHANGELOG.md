# Changelog

## Unreleased

- Add an AVISO pipeline PBS runner with ESP/input preflight, a frozen producing
  source archive, run manifests and stage status; reject changed-provenance resumes.
- Require all expected detection and surface-fit partitions before downstream
  fitting/tracking. Add verified pilot subsets and calendar-date legacy comparisons.

- Record the legacy AVISO output archive and verify the configured ESP functions
  match the current SEACOFS implementation; keep fresh outputs separate.

- On the AVISO working branch, correct `processing.date_origin` to 1990-01-01
  to match SEACOFS. Regenerate products made with the former 1950 setting.
- Add native AVISO daily snapshots, a Katana PBS runner, date/day and input
  consistency checks, and signature-verified image resumes.
- Add prominent links to SEACOFS dataset v1.0.0
  ([10.5281/zenodo.24486070](https://doi.org/10.5281/zenodo.24486070))
  and distinguish its data citation and licence from pipeline software v0.1.1.
- Add the dataset to software citation references and link the snapshot-rendering
  documentation to the published data.
- The publication-link and citation updates do not change the scientific kernels,
  dataset files or published version identifiers. AVISO changes above are
  unreleased and do not modify the published SEACOFS software or data.

## 0.1.1

This release updates the SEACOFS pipeline from external ESP v1.01 and supports
ESP v1.2. The recorded dataset-generation run used ESP v1.1
([Zenodo DOI](https://doi.org/10.5281/zenodo.24182671)); v1.2 has a byte-identical
computational `functions.py`, with presentation/notebook updates only.
Changing from ESP v1.01 can change fitted parameters and downstream results;
changing from v1.1 to v1.2 does not change the pipeline's ESP computational code.

- Rename the external ESP configuration key from `paths.esp_zonodo` to
  `paths.esp_root`. Existing configuration files must use the new key.
- Set the supplied Katana ESP path to
  `/home/z5297792/elliptical_streamfunction_parametrisation`.
- Update package version, citation metadata, and runner notebook instructions.
- Add a PBS batch script for all stages, with a configurable virtual environment
  and submission directory as its working directory; ignore PBS job logs.
- Document the local v0.1.0 results archive and the completed ESP v1.1 run;
  clarify that local inputs and generated datasets are outside the software release.
- Record the v0.1.1 Zenodo DOI (10.5281/zenodo.24457378) in the README and
  citation metadata, distinguishing it from the earlier v0.1.0 archive.

PBS job `9801291` reported completion on 17 November 2026 with exit status 0,
listing products through tilt analysis and confirming the intended ESP import
paths. See the README for execution evidence and memory-use qualifications.
This is not a numerical-equivalence test against ESP v1.01.
