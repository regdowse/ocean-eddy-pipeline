"""Completeness guards and non-destructive pilot subsets."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd
import xarray as xr
import yaml

from aviso_eddy_dataset.common import require_partitions
from aviso_eddy_dataset.config import load_config
from aviso_eddy_dataset import tracking

SCRIPT = Path(__file__).resolve().parents[1] / 'prepare_pilot.py'
spec = importlib.util.spec_from_file_location('prepare_aviso_pilot', SCRIPT)
pilot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pilot)
spec = importlib.util.spec_from_file_location('run_aviso_pipeline', SCRIPT.parent / 'run_pipeline.py')
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)
spec = importlib.util.spec_from_file_location('audit_aviso_pipeline', SCRIPT.parent / 'audit_run.py')
auditor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(auditor)


class ExecutionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.data = self.root / 'input'
        self.data.mkdir()
        self.config = self.root / 'config.yaml'
        self.config.write_text(yaml.safe_dump(dict(
            paths=dict(data_root=str(self.data), output_root=str(self.root/'output'), esp_root='/external'),
            parallel=dict(workers=2), processing=dict(date_origin='1990-01-01'),
        )))
        for year in [1994, 1995]:
            date = '1994-12-31' if year==1994 else '1995-01-01'
            xr.Dataset(dict(ugos=(('time','latitude','longitude'),np.ones((1,2,2))),
                            vgos=(('time','latitude','longitude'),np.zeros((1,2,2)))),
                       coords=dict(time=pd.to_datetime([date]),latitude=[-31.,-30.],longitude=[150.,151.])) \
                .to_netcdf(self.data / f'AVISO_0.125_EAC_{year}.nc')

    def test_preflight_rejects_cached_old_esp_and_wrong_origin(self):
        cfg=load_config(self.config)
        esp=self.root/'esp'
        esp.mkdir()
        (esp/'functions.py').write_text('# external module\n')
        cfg.raw['paths']['esp_root']=str(esp)
        with patch.object(runner,'load_doppio_functions',return_value=(lambda: None,lambda: None)):
            with self.assertRaisesRegex(RuntimeError,'Unexpected cached ESP'):
                runner.preflight(cfg)
        cfg.raw['processing']['date_origin']='1950-01-01'
        with self.assertRaisesRegex(ValueError,'1990-01-01'):
            runner.preflight(cfg)

    def test_legacy_comparison_uses_dates_and_locations_not_day_or_eddy_ids(self):
        cfg=load_config(self.config)
        legacy=self.root/'legacy'
        for year,date in [(1994,'1994-12-31'),(1995,'1995-01-01')]:
            day=(pd.Timestamp(date)-pd.Timestamp('1990-01-01')).days
            det=pd.DataFrame([dict(Day=day,Date=pd.Timestamp(date),Cyc='AE',
                                   nxc=10.,nyc=20.,nic=0,njc=0)])
            fit=det.rename(columns={'Cyc':'nCyc'}).assign(
                xc=10.,yc=20.,Omega0=1e-5,Omega=1e-5,w=2e-5,
                q11=1.,q12=0.,q22=1.,R=30.,Rc=40.,psi0=1.)
            for stage,df in [('detections',det),('surface_eddies',fit)]:
                for root,offset in [(cfg.output_root,0),(legacy,14610)]:
                    path=root/stage/f'source=AVISO_0.125_EAC_{year}.parquet'
                    path.parent.mkdir(parents=True,exist_ok=True)
                    df.assign(Day=df.Day+offset).to_parquet(path,index=False)
        dates=pd.to_datetime(['1994-12-31','1995-01-01'])
        df=pd.DataFrame(dict(Eddy=[1,1],Day=(dates-pd.Timestamp('1990-01-01')).days,
                             Date=dates,Cyc=['AE','AE'],Age=[2,2]))
        for stage,name in [('tracked','eddy_tracks'),('processed','eddy_dataset_processed')]:
            path=cfg.output_root/stage/f'{name}.parquet'
            path.parent.mkdir(parents=True,exist_ok=True)
            df.to_parquet(path,index=False)
        (legacy/'processed').mkdir()
        df.assign(Eddy=99,Day=df.Day+14610).to_parquet(legacy/'processed/eddy_dataset_processed.parquet',index=False)
        result=auditor.audit(self.config,legacy,require_processed=True)
        self.assertTrue(result['detection_candidates_identical'])
        self.assertEqual(result['matched_candidates'],2)
        self.assertEqual(result['new_tracks_crossing_year_boundary'],1)
        self.assertEqual(result['processed_legacy_date_window']['eddies'],1)
        self.assertEqual(result['processed_legacy_window_min_duration']['eddies'],0)
        self.assertEqual(result['fitting']['centre_displacement_km']['maximum'],0.)

    def test_missing_partition_stops_tracking_even_with_existing_tracks(self):
        cfg = load_config(self.config)
        folder = cfg.output_root / 'surface_eddies'
        folder.mkdir(parents=True)
        pd.DataFrame().to_parquet(folder / 'source=AVISO_0.125_EAC_1994.parquet')
        existing = cfg.output_root / 'tracked/eddy_tracks.parquet'
        existing.parent.mkdir()
        pd.DataFrame().to_parquet(existing)
        with self.assertRaisesRegex(FileNotFoundError, '1/2.*1995'):
            tracking.run(cfg)
        pd.DataFrame().to_parquet(folder / 'source=AVISO_0.125_EAC_1995.parquet')
        self.assertEqual(len(require_partitions(cfg, 'surface_eddies')), 2)
        self.assertTrue(tracking.clean(cfg).empty)

    def test_subset_preserves_velocity_values_and_crosses_year_boundary(self):
        originals = {}
        for year in [1994, 1995]:
            times = pd.date_range('1994-12-30', periods=2) if year==1994 else pd.date_range('1995-01-01',periods=2)
            data = np.arange(8,dtype=float).reshape(2,2,2) + year
            ds = xr.Dataset(dict(ugos=(('time','latitude','longitude'),data),
                                 vgos=(('time','latitude','longitude'),-data)),
                            coords=dict(time=times,latitude=[-30.,-31.],longitude=[150.,151.]))
            path = self.data/f'AVISO_0.125_EAC_{year}.nc'
            ds.to_netcdf(path)
            originals[path] = pilot.sha256(path)
        config = pilot.prepare(self.config,self.root/'pilot','1994-12-31','1995-01-01')
        cfg = load_config(config)
        self.assertEqual(cfg.raw['processing']['date_origin'],'1990-01-01')
        self.assertEqual(cfg.workers,2)
        for path,digest in originals.items():
            self.assertEqual(pilot.sha256(path),digest)
            with xr.open_dataset(cfg.data_root/path.name) as subset, xr.open_dataset(path) as original:
                self.assertEqual(subset.sizes['time'],1)
                np.testing.assert_array_equal(subset.ugos,original.ugos.sel(time=subset.time))
        with self.assertRaises(FileExistsError):
            pilot.prepare(self.config,self.root/'pilot','1994-12-31','1995-01-01')


if __name__ == '__main__':
    unittest.main()
