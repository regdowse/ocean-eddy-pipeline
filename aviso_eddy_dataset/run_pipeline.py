#!/usr/bin/env python3
"""Preflight, freeze source/provenance, and run AVISO stages in fresh processes."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import inspect
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "aviso_eddy_dataset/src"), str(ROOT / "src")]

import numpy as np
import pandas as pd

from aviso_eddy_dataset.common import find_data_files, open_aviso, source_file_by_day
from aviso_eddy_dataset.config import load_config
from aviso_eddy_dataset.grid import build_grid, native_velocity
from aviso_eddy_dataset.pipeline import STAGES
from seacofs_eddy_dataset.core.esp import load_doppio_functions


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path, value):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")
    temporary.replace(path)


def preflight(config):
    if any(not Path(value).expanduser().is_absolute() for value in config.raw['paths'].values()):
        raise ValueError("The batch runner requires absolute configuration paths")
    if config.raw.get("processing", {}).get("date_origin", "1990-01-01") != "1990-01-01":
        raise ValueError("AVISO production uses processing.date_origin: 1990-01-01")
    allocation = os.environ.get("PBS_NCPUS") or os.environ.get("NCPUS")
    if config.workers < 1 or (allocation and config.workers > int(allocation)):
        raise ValueError(f"Workers {config.workers} exceed CPU allocation {allocation}")
    files = find_data_files(config)
    output = config.output_root.resolve()
    protected = [config.data_root.resolve()]
    legacy = config.raw.get("validation", {}).get("legacy_root")
    if legacy:
        protected.append(Path(legacy).resolve())
    if any(output == p or p in output.parents or output in p.parents for p in protected):
        raise ValueError("Output must be separate from source inputs and the legacy archive")
    expected_esp = (Path(config.raw["paths"]["esp_root"]).expanduser() / "functions.py").resolve(strict=True)
    for function in load_doppio_functions(config):
        actual = Path(inspect.getfile(function)).resolve(strict=True)
        if actual != expected_esp:
            raise RuntimeError(f"Unexpected cached ESP function {actual}; expected {expected_esp}")
        inspect.signature(function).bind(*([None] * 8))
        print(f"ESP {function.__name__}: {actual}", flush=True)
    mapping = source_file_by_day(config)
    if mapping.empty or np.any(np.diff(mapping.index.to_numpy()) != 1):
        raise ValueError("Source times must form one continuous daily interval")
    dates = pd.Timestamp("1990-01-01") + pd.to_timedelta(mapping.index, unit="D")
    settings = config.raw.get("validation", {})
    for key, actual in [("start_date", dates.min()), ("end_date", dates.max())]:
        if key in settings and actual != pd.Timestamp(settings[key]):
            raise ValueError(f"Source {key}: {actual.date()}, expected {settings[key]}")
    variables = config.raw.get("variables", {})
    names = {n: variables.get(n, n) for n in ["longitude", "latitude", "time"]}
    reference = None
    for path in files:
        with open_aviso(path, config) as ds:
            coords = tuple(ds[names[n]].values for n in ["longitude", "latitude"])
            if reference is None:
                reference = tuple(np.array(a, copy=True) for a in coords)
            elif any(not np.array_equal(a, b) for a, b in zip(reference, coords)):
                raise ValueError(f"Coordinate grid differs in {path}")
            grid = build_grid(*coords)
            for component, default in [("u", "ugos"), ("v", "vgos")]:
                values = native_velocity(ds[variables.get(component, default)].isel({names['time']: 0}), grid)
                if not np.isfinite(values).any():
                    raise ValueError(f"No finite {component} values in first slice of {path}")
    print(f"Preflight: {len(files)} files, {len(mapping)} days, {dates.min().date()} to {dates.max().date()}", flush=True)
    return dict(
        esp_file=str(expected_esp), esp_sha256=sha256(expected_esp),
        input_files=[dict(path=str(p.resolve()), bytes=p.stat().st_size, sha256=sha256(p)) for p in files],
        source_days=len(mapping), start_date=str(dates.min().date()), end_date=str(dates.max().date()),
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--stages", default=",".join(stage.name for stage in STAGES))
    args = parser.parse_args(argv)
    selected = args.stages.split(",")
    if not selected or any(name not in {stage.name for stage in STAGES} for name in selected):
        parser.error("--stages must contain known comma-separated stage names")
    config = load_config(args.config)
    # Every source/configuration used by a run must have a reviewable producing commit.
    git = ["git", "-C", str(ROOT)]
    if subprocess.check_output(git + ["status", "--porcelain", "--untracked-files=all"], text=True).strip():
        raise RuntimeError("Commit working-tree changes before running; local ignored configs are allowed")
    commit = subprocess.check_output(git + ["rev-parse", "HEAD"], text=True).strip()
    identity = preflight(config)
    versions = {name: importlib.metadata.version(name) for name in
                ["numpy", "pandas", "scipy", "xarray", "netCDF4", "pyarrow", "joblib"]}
    identity.update(source_commit=commit, config_sha256=sha256(config.config_path),
                    configuration=config.raw, packages=versions, python=sys.version)
    provenance = config.output_root / "provenance"
    manifest_path = provenance / "run_manifest.json"
    if manifest_path.exists():
        previous = json.loads(manifest_path.read_text())
        if previous["identity"] != identity:
            raise ValueError("Run source/configuration/ESP/inputs changed; use a fresh output root")
        if sha256(provenance / "source.tar") != previous["source_archive_sha256"]:
            raise ValueError("Retained source archive changed")
    else:
        if config.output_root.exists() and any(config.output_root.iterdir()):
            raise ValueError("Existing output root has no producing manifest; choose a fresh directory")
        provenance.mkdir(parents=True)
        archive = subprocess.check_output(git + ["archive", "--format=tar", "HEAD"])
        (provenance / "source.tar").write_bytes(archive)
        (provenance / "generation_config.yaml").write_bytes(config.config_path.read_bytes())
        environment = subprocess.check_output([sys.executable, "-m", "pip", "freeze", "--all"], text=True)
        (provenance / "environment.txt").write_text(environment)
        write_json(manifest_path, dict(
            identity=identity, created_utc=datetime.now(timezone.utc).isoformat(),
            python=sys.version, python_executable=sys.executable,
            source_archive_sha256=sha256(provenance / "source.tar"),
            packages=versions,
            pbs_job_id=os.environ.get("PBS_JOBID"),
        ))
    # Execute from a private extraction of the retained archive, so worktree edits
    # made while the batch job runs cannot change its kernels or orchestration.
    import tempfile
    status_path = provenance / "execution_status.json"
    status = dict(started_utc=datetime.now(timezone.utc).isoformat(), stages=[], status="running")
    write_json(status_path, status)
    try:
        with tempfile.TemporaryDirectory(prefix="aviso-source-") as temporary:
            source = Path(temporary)
            with tarfile.open(provenance / "source.tar") as archive:
                archive.extractall(source)
            env = os.environ.copy()
            env["PYTHONPATH"] = os.pathsep.join([str(source / "aviso_eddy_dataset/src"), str(source / "src")])
            frozen_config = provenance / "generation_config.yaml"
            for name in selected:
                if sha256(identity["esp_file"]) != identity["esp_sha256"]:
                    raise RuntimeError("ESP file changed during the run")
                print(f"START {name}", flush=True)
                start = time.monotonic()
                subprocess.run([sys.executable, "-m", "aviso_eddy_dataset.cli", "run-stage", name,
                                "--config", str(frozen_config.resolve())], cwd=source, env=env, check=True)
                status["stages"].append(dict(name=name, elapsed_seconds=time.monotonic() - start))
                write_json(status_path, status)
                print(f"DONE {name}: {status['stages'][-1]['elapsed_seconds']:.1f} seconds", flush=True)
        status["status"] = "complete"
    except BaseException:
        status["status"] = "failed"
        status["error"] = traceback.format_exc()
        raise
    finally:
        status["finished_utc"] = datetime.now(timezone.utc).isoformat()
        write_json(status_path, status)
    print(f"AVISO stages complete; provenance: {provenance}", flush=True)


if __name__ == "__main__":
    main()
