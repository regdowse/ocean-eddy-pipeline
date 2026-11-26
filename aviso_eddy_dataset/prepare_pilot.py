#!/usr/bin/env python3
"""Create verified, separate date subsets and a corresponding AVISO run config."""
from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "aviso_eddy_dataset/src"), str(ROOT / "src")]
import numpy as np
import pandas as pd
import xarray as xr
import yaml
from aviso_eddy_dataset.common import find_data_files, open_aviso
from aviso_eddy_dataset.config import load_config


def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def prepare(config_path, work_root, start_date, end_date):
    config = load_config(config_path)
    root = Path(work_root).expanduser().resolve()
    if root.exists() and any(root.iterdir()):
        raise FileExistsError(f"Pilot directory must be new or empty: {root}")
    start, end = pd.Timestamp(start_date), pd.Timestamp(end_date)
    if start != start.normalize() or end != end.normalize() or start > end:
        raise ValueError("Pilot limits must be ordered calendar dates")
    variables = config.raw.get("variables", {})
    time = variables.get("time", "time")
    velocity = [variables.get("u", "ugos"), variables.get("v", "vgos")]
    inputs = root / "inputs"
    inputs.mkdir(parents=True)
    records, dates = [], []
    for source in find_data_files(config):
        with open_aviso(source, config) as ds:
            values = pd.DatetimeIndex(ds[time].values)
            selected = np.flatnonzero((values >= start) & (values <= end))
            if not selected.size:
                continue
            subset = ds[velocity].isel({time: selected}).load()
        source_sha = sha256(source)
        subset.attrs.update(original_source_file=str(source.resolve()),
                            original_source_sha256=source_sha,
                            subset_created_utc=datetime.now(timezone.utc).isoformat(),
                            time_coverage_start=str(values[selected[0]]),
                            time_coverage_end=str(values[selected[-1]]))
        output = inputs / source.name
        subset.to_netcdf(output)
        with xr.open_dataset(output) as reread:
            for name in subset.variables:
                np.testing.assert_array_equal(reread[name].values, subset[name].values)
        dates.extend(values[selected])
        records.append(dict(original_file=str(source.resolve()), original_sha256=source_sha,
                            subset_file=str(output), subset_sha256=sha256(output),
                            source_time_indices=selected.tolist(), days=int(selected.size)))
        print(f"Verified {output}: {selected.size} unchanged daily velocity slices", flush=True)
    observed = pd.DatetimeIndex(sorted(dates))
    expected = pd.date_range(start, end)
    if not observed.equals(expected):
        raise ValueError("Pilot inputs do not cover the requested daily interval exactly once")
    raw = copy.deepcopy(config.raw)
    raw['paths']['data_root'] = str(inputs)
    raw['paths']['output_root'] = str(root / "output")
    raw['processing']['date_origin'] = '1990-01-01'
    raw['parallel'].update(workers=min(2, len(records)), backend='process', skip_existing=True)
    raw['validation'] = dict(start_date=str(start.date()), end_date=str(end.date()),
                             legacy_root='/srv/scratch/z5297792/archive_aviso_eddy_dataset')
    (root / "config.yaml").write_text(yaml.safe_dump(raw, sort_keys=False))
    (root / "subset_manifest.json").write_text(json.dumps(dict(
        start_date=str(start.date()), end_date=str(end.date()), days=len(expected), files=records,
    ), indent=2) + '\n')
    print(f"Pilot configuration: {root / 'config.yaml'}", flush=True)
    return root / 'config.yaml'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=ROOT / 'aviso_eddy_dataset/config/example.yaml')
    parser.add_argument('--work-root', type=Path, required=True)
    parser.add_argument('--start-date', required=True)
    parser.add_argument('--end-date', required=True)
    args = parser.parse_args()
    prepare(args.config, args.work_root, args.start_date, args.end_date)


if __name__ == '__main__':
    main()
