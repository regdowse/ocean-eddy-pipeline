#!/usr/bin/env python3
"""Validate AVISO run tables and compare matched calendar dates with legacy data."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'aviso_eddy_dataset/src'), str(ROOT / 'src')]
import numpy as np
import pandas as pd
from aviso_eddy_dataset.common import require_partitions, source_file_by_day
from aviso_eddy_dataset.config import load_config


def population(df):
    if df.empty:
        return dict(rows=0, eddies=0, tracks_by_cyclonicity={})
    return dict(rows=len(df), eddies=int(df.Eddy.nunique()),
                tracks_by_cyclonicity={str(k):int(v) for k,v in df.groupby('Cyc').Eddy.nunique().items()})


def audit(config_path, legacy_root, require_processed=False):
    cfg=load_config(config_path)
    mapping=source_file_by_day(cfg)
    first=pd.Timestamp('1990-01-01')+pd.Timedelta(days=int(mapping.index.min()))
    last=pd.Timestamp('1990-01-01')+pd.Timedelta(days=int(mapping.index.max()))
    tables={}
    for stage in ['detections','surface_eddies']:
        tables[stage]=pd.concat([pd.read_parquet(p) for p in require_partitions(cfg,stage)],ignore_index=True)
    for stage,name in [('tracked','eddy_tracks'),('processed','eddy_dataset_processed')]:
        tables[stage]=pd.read_parquet(cfg.output_root/stage/f'{name}.parquet')
    checks={}
    for name,df in tables.items():
        dates=pd.to_datetime(df.Date)
        if not dates.eq(pd.Timestamp('1990-01-01')+pd.to_timedelta(df.Day,unit='D')).all():
            raise ValueError(f'{name}: incorrect Date/Day mapping')
        if not df.Day.isin(mapping.index).all():
            raise ValueError(f'{name}: rows outside source time coverage')
        if 'Eddy' in df and df.duplicated(['Eddy','Day']).any():
            raise ValueError(f'{name}: duplicate eddy-day keys')
        checks[name]=dict(rows=len(df),days_with_rows=int(dates.nunique()))
    if len(tables['detections'])!=len(tables['surface_eddies']):
        raise ValueError('Surface fitting did not retain one attempt row per detection')
    finite_centres=np.isfinite(tables['surface_eddies'].xc)&np.isfinite(tables['surface_eddies'].yc)
    checks['surface_eddies']['finite_centres']=int(finite_centres.sum())
    if len(tables['detections']) and not finite_centres.any():
        raise ValueError('All surface fits failed; investigate ESP and native-grid fitting before continuing')
    processed=tables['processed']
    if require_processed and processed.empty:
        raise ValueError('Pilot unexpectedly retained no processed eddies')
    if not processed.empty:
        if not processed.Age.eq(processed.groupby('Eddy').Eddy.transform('count')).all():
            raise ValueError('Incorrect processed Age values')
        for eddy,group in processed.groupby('Eddy'):
            if not np.all(np.diff(np.sort(group.Day))==1) or group.Cyc.nunique()!=1:
                raise ValueError(f'Inconsistent processed track {eddy}')
    legacy=Path(legacy_root)
    legacy_tables={}
    for stage in ['detections','surface_eddies']:
        frames=[]
        for path in require_partitions(cfg,stage):
            old=pd.read_parquet(legacy/stage/path.name)
            frames.append(old.loc[pd.to_datetime(old.Date).between(first,last)].copy())
        legacy_tables[stage]=pd.concat(frames,ignore_index=True)
    old_processed=pd.read_parquet(legacy/'processed/eddy_dataset_processed.parquet')
    old_processed=old_processed.loc[pd.to_datetime(old_processed.Date).between(first,last)].copy()
    keys=['Date','nxc','nyc','nic','njc','Cyc']
    new=tables['detections'][keys].sort_values(keys).reset_index(drop=True)
    old=legacy_tables['detections'][keys].sort_values(keys).reset_index(drop=True)
    identical=len(new)==len(old)
    if identical:
        try:
            pd.testing.assert_frame_equal(new,old,check_dtype=False,check_exact=True)
        except AssertionError:
            identical=False
    fits=tables['surface_eddies'].rename(columns={'nCyc':'Cyc'})
    old_fits=legacy_tables['surface_eddies'].rename(columns={'nCyc':'Cyc'})
    matched=fits.merge(old_fits,on=keys,suffixes=('_new','_legacy'),validate='one_to_one')
    metrics={}
    for field in ['xc','yc','Omega0','Omega','w','q11','q12','q22','R','Rc','psi0']:
        a,b=matched[f'{field}_new'],matched[f'{field}_legacy']
        valid=np.isfinite(a)&np.isfinite(b)
        metrics[field]=dict(matched_finite_pairs=int(valid.sum()),
                            median_absolute_difference=float((a[valid]-b[valid]).abs().median()) if valid.any() else None)
    new_valid=np.isfinite(matched.xc_new)&np.isfinite(matched.yc_new)
    old_valid=np.isfinite(matched.xc_legacy)&np.isfinite(matched.yc_legacy)
    daily=pd.DataFrame(index=pd.date_range(first,last))
    for label,df in [('new_detections',tables['detections']),('legacy_detections',legacy_tables['detections']),
                     ('new_processed',processed),('legacy_processed',old_processed)]:
        daily[label]=pd.to_datetime(df.Date).value_counts().reindex(daily.index,fill_value=0)
    crossyear=0
    if not processed.empty:
        crossyear=int((processed.assign(year=pd.to_datetime(processed.Date).dt.year)
                       .groupby('Eddy').year.nunique()>1).sum())
    report=dict(start_date=str(first.date()),end_date=str(last.date()),source_days=len(mapping),
                stage_counts=checks,detection_candidates_identical=identical,
                legacy_day_origin='1950-01-01',new_day_origin='1990-01-01',
                matched_candidates=len(matched),
                fitting=dict(new_finite_centres=int(new_valid.sum()),legacy_finite_centres=int(old_valid.sum()),
                             recovered_centres=int((new_valid&~old_valid).sum()),lost_centres=int((old_valid&~new_valid).sum()),
                             parameters=metrics),
                processed_new=population(processed),processed_legacy_date_window=population(old_processed),
                new_tracks_crossing_year_boundary=crossyear,
                qualifications=['Legacy tracks span the full record; pilot track durations and boundary retention are censored.',
                                'Eddy IDs and raw Day values are not correspondence keys.',
                                'Fit comparisons use identical original candidate locations, dates and cyclonicity.'])
    out=cfg.output_root/'validation'
    out.mkdir(exist_ok=True)
    daily.to_csv(out/'daily_counts.csv',index_label='Date')
    matched.to_parquet(out/'matched_surface_fits.parquet',index=False)
    (out/'comparison.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    print(json.dumps(report,indent=2,allow_nan=False),flush=True)
    if not identical:
        raise ValueError('Detection candidates differ from legacy; inspect before attributing changes to ESP')
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',type=Path,required=True)
    parser.add_argument('--legacy-root',type=Path,required=True)
    parser.add_argument('--require-processed',action='store_true')
    args=parser.parse_args()
    audit(args.config,args.legacy_root,args.require_processed)
