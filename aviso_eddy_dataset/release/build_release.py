#!/usr/bin/env python3
"""Assemble and verify the AVISO data/source deposit without modifying run outputs."""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import html
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import zipfile

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'aviso_eddy_dataset/src'), str(ROOT / 'src')]
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import xarray as xr
import yaml
from aviso_eddy_dataset.grid import build_grid

DOI = '10.5281/zenodo.24575702'
VERSION = '1.0.0'
TAG = 'aviso-dataset-v1.0.0'
TITLE = 'AVISO-derived mesoscale eddy dataset for the East Australian Current and Tasman Sea (1994–2019)'
HERE = Path(__file__).resolve().parent


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for block in iter(lambda:handle.read(8*1024*1024),b''):
            h.update(block)
    return h.hexdigest()


def build(data_root, output_root):
    data = Path(data_root).resolve()
    out = Path(output_root).resolve()
    if data == out or data in out.parents or out in data.parents:
        raise ValueError('Release output must be separate from producing data')
    if out.exists() and any(out.iterdir()):
        raise FileExistsError(f'Release output must be new or empty: {out}')
    run = json.loads((data/'provenance/run_manifest.json').read_text())
    status = json.loads((data/'provenance/execution_status.json').read_text())
    validation = json.loads((data/'validation/summary.json').read_text())
    if status['status'] != 'complete':
        raise ValueError('Producing run is not complete')
    source = data/'provenance/source.tar'
    if sha256(source) != run['source_archive_sha256']:
        raise ValueError('Producing source archive differs from its run manifest')
    with tarfile.open(source) as archive:
        for path in sorted(list((ROOT/'src').rglob('*.py'))+list((ROOT/'aviso_eddy_dataset/src').rglob('*.py'))):
            name=str(path.relative_to(ROOT))
            if archive.extractfile(name).read()!=path.read_bytes():
                raise ValueError(f'Scientific source changed after generation: {name}')
    expected = {'detections':26,'surface_eddies':26,'tracked':1,'processed':1}
    inventory=[]
    for stage,count in expected.items():
        files=sorted((data/stage).glob('*.parquet'))
        if len(files)!=count:
            raise ValueError(f'Unexpected {stage} file count')
        rows=sum(pq.ParquetFile(p).metadata.num_rows for p in files)
        if rows!=validation['stage_counts'][stage]['rows']:
            raise ValueError(f'{stage} row count changed after validation')
        for p in files:
            inventory.append(dict(path=str(p.relative_to(data)),bytes=p.stat().st_size,
                                  sha256=sha256(p),rows=pq.ParquetFile(p).metadata.num_rows))
    processed=pd.read_parquet(data/'processed/eddy_dataset_processed.parquet')
    if processed.duplicated(['Eddy','Day']).any() or len(processed)!=454519 or processed.Eddy.nunique()!=9002:
        raise ValueError('Processed table does not match this v1.0.0 release')
    if not processed.Date.eq(pd.Timestamp('1990-01-01')+pd.to_timedelta(processed.Day,unit='D')).all():
        raise ValueError('Incorrect date/day convention')
    dictionary=list(csv.DictReader((HERE/'variables.csv').open(newline='')))
    known={row['field'] for row in dictionary}
    for row in dictionary:
        if None in row or set(row)!={'field','stages','units','description'}:
            raise ValueError('Invalid variable dictionary CSV')
    for row in inventory:
        missing=set(pq.ParquetFile(data/row['path']).schema.names)-known
        if missing:
            raise ValueError(f'Undocumented variables: {missing}')
    package=out/f'aviso_eddy_dataset_v{VERSION}'
    package.mkdir(parents=True)
    originals={}
    for directory in ['detections','surface_eddies','tracked','processed','provenance','validation']:
        for p in sorted((data/directory).rglob('*')):
            if not p.is_file():
                continue
            if p.suffix=='.tmp':
                raise ValueError(f'Unfinished temporary output: {p}')
            relative=p.relative_to(data)
            target=package/relative
            target.parent.mkdir(parents=True,exist_ok=True)
            originals[str(relative)]=sha256(p)
            shutil.copy2(p,target)
    for name in ['README.md','CITATION.cff','LICENSE-data.txt','variables.csv']:
        shutil.copyfile(HERE/name,package/name)
    shutil.copyfile(ROOT/'LICENSE',package/'LICENSE-code.txt')
    shutil.copyfile(data/'provenance/generation_config.yaml',package/'generation_config.yaml')
    export=(data/'provenance/environment.txt').read_text()
    pins=[line for line in export.splitlines() if line and not line.startswith(('#','-e ')) and ' @ file:' not in line]
    (package/'requirements-generation.txt').write_text('\n'.join(pins)+'\n')
    cfg=yaml.safe_load((package/'generation_config.yaml').read_text())
    first=Path(run['identity']['input_files'][0]['path'])
    if sha256(first)!=run['identity']['input_files'][0]['sha256']:
        raise ValueError('Reference input changed since generation')
    with xr.open_dataset(first) as ds:
        original_attrs=dict(ds.attrs)
        grid=build_grid(ds.longitude.values,ds.latitude.values)
    geometry=xr.Dataset(
        data_vars=dict(longitude=('x',grid.longitude),latitude=('y',grid.latitude),
                       source_longitude_index=('x',grid.lon_order),source_latitude_index=('y',grid.lat_order)),
        coords=dict(x=grid.x_grid,y=grid.y_grid),
        attrs=dict(title='Native AVISO coordinate reference for the derived eddy dataset',
                   dataset_doi=DOI,source_product_doi='10.48670/moi-00148',
                   source_reference_file=first.name,source_reference_sha256=run['identity']['input_files'][0]['sha256'],
                   coordinate_construction='Increasing axes; cumulative spherical distances at mean latitude/longitude; Earth radius 6357 km; not a standard projection',
                   velocity_convention='Unrotated absolute geostrophic eastward/northward components',
                   source_index_convention='Zero-based index mapping from increasing coordinates to original source array order',
                   licence='Native source coordinates retain Copernicus Marine terms; see LICENSE-data.txt'))
    for name,units in [('x','km'),('y','km'),('longitude','degrees_east'),('latitude','degrees_north'),('source_longitude_index','1'),('source_latitude_index','1')]:
        geometry[name].attrs['units']=units
    geometry.to_netcdf(package/'static_grid.nc')
    with xr.open_dataset(package/'static_grid.nc') as saved:
        for name in geometry.variables:
            np.testing.assert_array_equal(saved[name].values,geometry[name].values)
    (package/'provenance/source_product_metadata.json').write_text(json.dumps(original_attrs,indent=2,default=str)+'\n')
    release_commit=subprocess.check_output(['git','-C',str(ROOT),'rev-parse','HEAD'],text=True).strip()
    manifest=dict(dataset_doi=DOI,dataset_version=VERSION,release_tag=TAG,
                  generated_source_commit=run['identity']['source_commit'],documentation_release_commit=release_commit,
                  source_archive_sha256=run['source_archive_sha256'],
                  esp_sha256=run['identity']['esp_sha256'],
                  release_created_utc=datetime.now(timezone.utc).isoformat(),
                  table_inventory=inventory,processed_rows=len(processed),eddy_count=int(processed.Eddy.nunique()),
                  final_missing_values={k:int(v) for k,v in processed.isna().sum().items()},
                  source_data_root=str(data),original_output_hashes=originals,
                  files={str(p.relative_to(package)):sha256(p) for p in sorted(package.rglob('*')) if p.is_file()})
    (package/'release_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    hashes={str(p.relative_to(package)):sha256(p) for p in sorted(package.rglob('*')) if p.is_file()}
    (package/'checksums.sha256').write_text(''.join(f'{digest}  {name}\n' for name,digest in hashes.items()))
    archive_path=out/f'aviso_eddy_dataset_v{VERSION}.zip'
    with zipfile.ZipFile(archive_path,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6,allowZip64=True) as archive:
        for p in sorted(package.rglob('*')):
            if p.is_file():archive.write(p,p.relative_to(out))
    with zipfile.ZipFile(archive_path) as archive:
        if archive.testzip() is not None:raise ValueError('ZIP CRC integrity failed')
        for name,digest in hashes.items():
            with archive.open(f'{package.name}/{name}') as handle:
                h=hashlib.sha256()
                for block in iter(lambda:handle.read(8*1024*1024),b''):h.update(block)
            if h.hexdigest()!=digest:raise ValueError(f'Packaged file hash mismatch: {name}')
    for name,digest in originals.items():
        if sha256(data/name)!=digest:raise ValueError(f'Original output changed: {name}')
    shutil.copyfile(package/'README.md',out/'README.md')
    shutil.copyfile(package/'CITATION.cff',out/'CITATION.cff')
    upload_files=[archive_path,out/'README.md',out/'CITATION.cff']
    (out/'UPLOAD_CHECKSUMS.sha256').write_text(''.join(f'{sha256(p)}  {p.name}\n' for p in upload_files))
    metadata=zenodo_metadata(run['identity']['source_commit'])
    (out/'zenodo_metadata.json').write_text(json.dumps({'metadata':metadata},indent=2,ensure_ascii=False)+'\n')
    (out/'ZENODO_UPLOAD_GUIDE.md').write_text(upload_guide(metadata))
    (out/'package_verification.json').write_text(json.dumps(dict(
        verified=True,zip_bytes=archive_path.stat().st_size,zip_sha256=sha256(archive_path),
        archive_files=len(hashes)+1,original_outputs_preserved=len(originals),
        checks=['Expected partitions/row counts','Complete variable dictionary','Static grid round trip',
                'Producing source archive hash','Current scientific source matches producing snapshot',
                'All ZIP CRCs','All packaged SHA-256 hashes','Original run outputs unchanged'],
        uploaded_or_published=False),indent=2)+'\n')
    print(json.dumps(dict(output=str(out),zip=str(archive_path),bytes=archive_path.stat().st_size,
                          sha256=sha256(archive_path),data_source_commit=run['identity']['source_commit'],
                          release_commit=release_commit,verified=True),indent=2),flush=True)


def zenodo_metadata(commit):
    description=('This dataset contains velocity-defined surface mesoscale eddy detections, fitted parameters and tracks '
                 'derived from daily AVISO/SSALTO-DUACS absolute geostrophic velocities in the East Australian Current '
                 'and Tasman Sea region. Input coverage is 2 January 1994–28 February 2019 (9,189 days); the native '
                 '0.125-degree grid spans 145.0625–162.9375°E and 42.9375–25.0625°S. '
                 'The processed population contains 9,002 eddies (4,114 anticyclonic and 4,888 cyclonic), contributing '
                 '454,519 eddy-days. The workflow uses Nencioli candidate detection, native-grid DOPPIO/ESP fitting, '
                 'continuous cross-year tracking and quality control. Processed values can be smoothed or interpolated; '
                 'there are no vertical-profile or tilt products. '
                 'The release includes all four processing stages, a coordinate reference, variable dictionary, '
                 'generation configuration, environment, validation summary, checksums and the exact producing source '
                 f'archive from commit {commit}. The single dataset DOI identifies both the data and preserved source. '
                 'Original velocity fields and the external ESP dependency are not included. '
                 'Generated using E.U. Copernicus Marine Service Information; https://doi.org/10.48670/moi-00148. '
                 'Derived eddy tables/documentation are CC BY 4.0; preserved pipeline code is MIT; source-coordinate '
                 'components retain Copernicus Marine terms. See the component licence files.')
    return dict(upload_type='dataset',title=TITLE,version=VERSION,language='eng',
                description='<p>'+html.escape(description)+'</p>',access_right='open',license='cc-by-4.0',
                creators=[dict(name='Dowse, Reg Watson',affiliation='University of New South Wales',orcid='0009-0000-6856-3115')],
                keywords=['mesoscale eddies','AVISO','SSALTO/DUACS','Copernicus Marine','East Australian Current','Tasman Sea','altimetry','geostrophic velocity','eddy tracking','DOPPIO','elliptical streamfunction parametrisation'],
                related_identifiers=[
                    dict(identifier='10.48670/moi-00148',relation='isDerivedFrom',resource_type='dataset',scheme='doi'),
                    dict(identifier=f'https://github.com/regdowse/ocean-eddy-pipeline/tree/{commit}',relation='references',resource_type='software',scheme='url'),
                    dict(identifier=f'https://github.com/regdowse/ocean-eddy-pipeline/tree/{TAG}',relation='references',resource_type='software',scheme='url'),
                    dict(identifier='10.5281/zenodo.24182671',relation='references',resource_type='software',scheme='doi'),
                    dict(identifier='10.5281/zenodo.24457378',relation='references',resource_type='software',scheme='doi'),
                    dict(identifier='10.5194/egusphere-2026-3599',relation='references',resource_type='publication-preprint',scheme='doi'),
                    dict(identifier='10.1175/2009JTECHO725.1',relation='references',resource_type='publication-article',scheme='doi')])


def upload_guide(metadata):
    description=html.unescape(metadata['description'][3:-4])
    text=f'''# Zenodo upload guide: AVISO dataset v{VERSION}

Use your existing draft with reserved DOI **{DOI}**. Do not create another DOI.
The files have been prepared locally; nothing has been uploaded or published.

## Files to upload

Upload these four files from this directory:

- `aviso_eddy_dataset_v{VERSION}.zip` — complete dataset and preserved source.
- `README.md` — same README as inside the ZIP, visible without downloading it.
- `CITATION.cff` — machine-readable citation for the combined deposit.
- `UPLOAD_CHECKSUMS.sha256` — SHA-256 checksums for the preceding three files.

Do not upload the unpacked staging directory as well. `zenodo_metadata.json`
is a reference for entering the form, not an additional research-data upload.

## Basic fields

| Field | Enter |
| --- | --- |
| Resource type | Dataset |
| DOI | Keep the already reserved {DOI} |
| Title | {TITLE} |
| Version | {VERSION} |
| Creator | Dowse, Reg Watson |
| ORCID | 0009-0000-6856-3115 |
| Affiliation | University of New South Wales |
| Language | English |
| Visibility/access | Public / Open access |
| Licence | Creative Commons Attribution 4.0 International (CC BY 4.0) |
| Publication date | Date you actually publish, not the extraction date |
| Publisher, if requested | Zenodo |

The component-specific MIT code and upstream coordinate terms are documented in
the licence files. Confirm the creator/affiliation fields match how you want to
be credited before publication.

## Description — paste this

{description}

## Keywords

{'; '.join(metadata['keywords'])}

## Related works / related identifiers

Enter the following relationships *from this AVISO dataset to the linked item*:

| Identifier | Scheme | Relationship | Resource type |
| --- | --- | --- | --- |
'''
    for row in metadata['related_identifiers']:
        label='Is derived from' if row['relation']=='isDerivedFrom' else 'References'
        text+=f"| {row['identifier']} | {row['scheme'].upper()} | {label} | {row['resource_type']} |\n"
    return text+'''
If the form provides GitHub/repository fields, use the version-tag URL above.
This is a new AVISO dataset record, not a new version of the SEACOFS dataset.
Keep the single reserved dataset DOI; there is no separate new software DOI.

## Before clicking Publish

Confirm all four uploads completed, the DOI/title/version/creator are correct,
and the preview displays the Copernicus acknowledgement. Then publish this
existing draft. Afterwards send the public record link so the landing page can
be checked. Existing data files and the preserving source have not been rerun.
'''


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-root',type=Path,default=Path('/srv/scratch/z5297792/aviso_eddy_dataset'))
    parser.add_argument('--output-root',type=Path,default=Path('/srv/scratch/z5297792/aviso_eddy_dataset_release_v1.0.0'))
    args=parser.parse_args()
    build(args.data_root,args.output_root)
