"""AVISO source orientation, day mapping, coverage and safe PNG resumes."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd
from PIL import Image
import xarray as xr
import yaml


MODULE = (Path(__file__).resolve().parents[1]
          / "notebooks/daily_snapshots/render_frames.py")
spec = importlib.util.spec_from_file_location("aviso_render_frames", MODULE)
frames = importlib.util.module_from_spec(spec)
spec.loader.exec_module(frames)


class AvisoSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="aviso-snapshots-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.source = self.root / "source"
        self.source.mkdir()
        self.output = self.root / "output"
        (self.output / "processed").mkdir(parents=True)
        self.frames = self.root / "frames"
        self.times = pd.date_range("1994-12-31", periods=3)
        self.days = (self.times - pd.Timestamp("1990-01-01")).days
        # Both axes descend. Values distinguish every cell and component.
        self.lon = np.array([165., 160., 155., 150.])
        self.lat = np.array([-30., -35., -40.])
        self.u = np.arange(36, dtype=float).reshape(3, 3, 4) / 100
        self.v = -self.u / 2
        self.paths = []
        for year, indices in [(1994, [0]), (1995, [1, 2])]:
            path = self.source / f"AVISO_0.125_EAC_{year}.nc"
            xr.Dataset(
                {"ugos": (("time", "latitude", "longitude"), self.u[indices]),
                 "vgos": (("time", "latitude", "longitude"), self.v[indices])},
                coords={"time": self.times[indices], "longitude": self.lon,
                        "latitude": self.lat},
            ).to_netcdf(path)
            self.paths.append(path)
        self.processed = self.output / "processed/eddy_dataset_processed.parquet"
        self.table = pd.DataFrame([
            dict(Eddy=1, Day=self.days[i], Date=self.times[i], Cyc="AE",
                 xc=250., yc=300., q11=1., q12=.1, q22=1.5, Rc=120.)
            for i in [0, 2]
        ])
        self.table.to_parquet(self.processed, index=False)
        self.config = self.root / "config.yaml"
        self.config.write_text(yaml.safe_dump({
            "paths": {"data_root": str(self.source), "output_root": str(self.output),
                      "esp_root": "/not-needed-for-rendering"},
            "processing": {"date_origin": "1990-01-01"},
        }))
        self.args = ["--config", str(self.config), "--output-dir", str(self.frames),
                     "--dpi", "30"]

    def manifest(self):
        return pd.read_csv(self.frames / "frame_manifest.csv")

    def test_native_velocities_year_boundary_empty_days_and_resume(self):
        original = frames.FrameRenderer.render
        captured = []

        def capture(renderer, u, v, rows, day, date, path, signature):
            captured.append((u.copy(), v.copy(), len(rows), day, date))
            return original(renderer, u, v, rows, day, date, path, signature)

        with patch.object(frames.FrameRenderer, "render", capture):
            frames.main(self.args)
        manifest = self.manifest()
        self.assertEqual(manifest.date.tolist(), [f"{t:%Y-%m-%d}" for t in self.times])
        self.assertEqual(manifest.day.tolist(), list(self.days))
        self.assertEqual(manifest.AE.tolist(), [1, 0, 1])
        self.assertEqual(manifest.time_index.tolist(), [0, 0, 1])
        self.assertEqual(manifest.status.tolist(), ["written"] * 3)
        for i, (u, v, count, day, date) in enumerate(captured):
            np.testing.assert_array_equal(u, self.u[i].T[::-1, ::-1])
            np.testing.assert_array_equal(v, self.v[i].T[::-1, ::-1])
            self.assertEqual(count, [1, 0, 1][i])
            self.assertEqual(day, self.days[i])
            self.assertEqual(date, self.times[i])
        paths = [Path(p) for p in manifest.frame_path]
        mtimes = [p.stat().st_mtime_ns for p in paths]
        for p in paths:
            with Image.open(p) as image:
                self.assertEqual(image.size, (270, 300))
                self.assertTrue(image.info["render_signature"])
                image.verify()
        with patch.object(frames.FrameRenderer, "render", side_effect=AssertionError("redraw")):
            frames.main(self.args)
        self.assertEqual(self.manifest().status.tolist(), ["skipped"] * 3)
        self.assertEqual([p.stat().st_mtime_ns for p in paths], mtimes)

    def test_wrong_day_origin_and_duplicate_keys_fail_before_image_writes(self):
        bad = self.table.copy()
        bad.Day += 14610
        bad.to_parquet(self.processed, index=False)
        with self.assertRaisesRegex(ValueError, "Date/Day"):
            frames.main(self.args)
        self.assertFalse(self.frames.exists())
        pd.concat([self.table, self.table.iloc[:1]]).to_parquet(self.processed, index=False)
        with self.assertRaisesRegex(ValueError, "duplicate.*Eddy"):
            frames.main(self.args)

    def test_duplicate_source_dates_and_changed_grids_fail_before_writes(self):
        with xr.open_dataset(self.paths[1]) as ds:
            data = ds.load()
        data.assign_coords(time=self.times[[0, 2]]).to_netcdf(self.paths[1], mode="w")
        with self.assertRaisesRegex(ValueError, "Duplicate AVISO day"):
            frames.main(self.args)
        self.assertFalse(self.frames.exists())
        data.assign_coords(longitude=self.lon + 1).to_netcdf(self.paths[1], mode="w")
        with self.assertRaisesRegex(ValueError, "coordinate grid differs"):
            frames.main(self.args)
        self.assertFalse(self.frames.exists())

    def test_inclusive_dates_settings_changes_and_corrupted_frames(self):
        args = self.args + ["--start-date", "1995-01-01", "--end-date", "1995-01-01"]
        frames.main(args)
        self.assertEqual(self.manifest().date.tolist(), ["1995-01-01"])
        with self.assertRaisesRegex(ValueError, "settings differ"):
            frames.main(args + ["--speed-vmax", "2"])
        frame = Path(self.manifest().frame_path.iloc[0])
        frame.write_bytes(b"incomplete png")
        with self.assertRaises(OSError):
            frames.main(args)
        frames.main(args + ["--overwrite"])
        with Image.open(frame) as image:
            image.verify()


if __name__ == "__main__":
    unittest.main()
