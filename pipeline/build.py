import argparse
import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

from .aggregate import aggregate
from .collect import read_records
from .model import ROOT, atomic_json, merge_records


def build(data_dir,output):
    data_dir=Path(data_dir);output=Path(output)
    if output.resolve() in {ROOT.resolve(),data_dir.resolve()}:
        raise ValueError('Build output must not replace source or input data')
    if not (data_dir/'state.json').exists():
        raise ValueError('No successful snapshot. Run python3 -m pipeline.collect first.')
    state=json.loads((data_dir/'state.json').read_text())
    overrides=json.loads((ROOT/'config/overrides.json').read_text())
    records=merge_records(read_records(data_dir),[],overrides)
    result=aggregate(records,state,overrides)
    fingerprint=hashlib.sha256(state['content_hash'].encode())
    for folder in ['web','config','pipeline']:
        for file in sorted((ROOT/folder).rglob('*')):
            if file.is_file() and '__pycache__' not in file.parts and file.suffix!='.pyc':
                fingerprint.update(str(file.relative_to(ROOT)).encode());fingerprint.update(file.read_bytes())
    build_id=fingerprint.hexdigest()[:24]
    result['build_id']=build_id
    try:
        build_code_sha=os.environ.get('GITHUB_SHA') or subprocess.check_output(
            ['git','rev-parse','HEAD'],cwd=ROOT,text=True,stderr=subprocess.DEVNULL).strip()
    except (OSError,subprocess.CalledProcessError):
        build_code_sha=state['code_sha']
    # Build in a staging directory so incomplete builds cannot replace the previous output.
    stage=output.with_name(output.name+'-staging')
    if stage.exists():shutil.rmtree(stage)
    shutil.copytree(ROOT/'web',stage)
    for route in ['research','archive','methodology']:
        (stage/route).mkdir();shutil.copyfile(stage/'index.html',stage/route/'index.html')
    full=result.pop('records');index=[];shards={}
    for r in full:
        shard=f'{r["source"]}-{r["id"].split(":")[-1][0]}.json'
        shards.setdefault(shard,{})[r['id']]=r
        small={k:v for k,v in r.items() if k not in {'abstract','events','provenance','citations','citations_as_of','version'}}
        small['detail_shard']='/data/details/'+shard
        index.append(small)
    for name,rows in shards.items():atomic_json(stage/'data/details'/name,rows)
    atomic_json(stage/'data/index.json',dict(run_id=state['run_id'],build_id=build_id,records=index))
    atomic_json(stage/'data/summary.json',result)
    config=json.loads((ROOT/'config/sources.json').read_text())
    sources=[]
    for s in config:
        status=state['sources'].get(s['id'],{'status':'not_configured','message':'Not collected yet.'})
        entry={k:v for k,v in s.items() if k in {'id','name','kind','url','required','enabled','note'}}
        entry.update(status);sources.append(entry)
    manifest=dict(schema_version=1,run_id=state['run_id'],build_id=build_id,generated_at=state['last_success'],
        content_hash=state['content_hash'],code_sha=build_code_sha,collection_code_sha=state['code_sha'],sources=sources,
        snapshot_type=state.get('snapshot_type','live'),status=state['status'])
    atomic_json(stage/'data/manifest.json',manifest)
    if output.exists():shutil.rmtree(output)
    stage.replace(output)
    print(f'Built {len(index)} records, {len(shards)} detail shards, 4 routes → {output}')


def main():
    p=argparse.ArgumentParser();p.add_argument('--data-dir',default=str(ROOT/'data'));p.add_argument('--output',default=str(ROOT/'dist'))
    a=p.parse_args();build(a.data_dir,a.output)


if __name__=='__main__':main()
