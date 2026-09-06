"""Validate the static artifact before upload, including cross-file data identity."""
import argparse
import json
from pathlib import Path
from html.parser import HTMLParser


class Assets(HTMLParser):
    def __init__(self):super().__init__();self.paths=[]
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        value=attrs.get('src') or (attrs.get('href') if tag=='link' else None)
        if value and value.startswith('/'):self.paths.append(value)


def validate(directory,production=False):
    root=Path(directory)
    for path in ['index.html','research/index.html','archive/index.html','methodology/index.html','404.html','_headers']:
        assert (root/path).is_file(),f'Missing {path}'
    parser=Assets();parser.feed((root/'index.html').read_text())
    for path in parser.paths:assert (root/path.lstrip('/')).is_file(),f'Missing asset {path}'
    summary=json.loads((root/'data/summary.json').read_text());index=json.loads((root/'data/index.json').read_text());manifest=json.loads((root/'data/manifest.json').read_text())
    assert summary['run_id']==index['run_id']==manifest['run_id'],'Mixed data snapshots'
    assert summary['build_id']==index['build_id']==manifest['build_id'],'Mixed application builds'
    if production:assert manifest['snapshot_type']=='live','Fixture data must never be deployed'
    ids={r['id'] for r in index['records']}
    assert len(ids)==len(index['records']),'Duplicate record identifiers'
    assert len(ids)==summary['totals']['records'],'Index count differs from totals'
    for r in index['records']:
        assert (root/r['detail_shard'].lstrip('/')).is_file(),'Missing detail shard'
        assert set(r['linked_record_ids'])<=ids,'Dangling linked record'
    for shard in (root/'data/details').glob('*.json'):
        for key,record in json.loads(shard.read_text()).items():assert key==record['id'] and key in ids
    files=[p for p in root.rglob('*') if p.is_file()]
    assert len(files)<20000,'Split or migrate data before the Pages asset limit'
    assert max(p.stat().st_size for p in files)<25*1024*1024,'Oversized Pages asset'
    print(f'Validated {len(files)} files, {len(ids)} records, matching run {summary["run_id"]}')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('directory',nargs='?',default='dist');p.add_argument('--production',action='store_true');a=p.parse_args();validate(a.directory,a.production)
