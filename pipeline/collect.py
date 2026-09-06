import argparse
import hashlib
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .adapters import ADAPTERS, Fetcher, enrich_openalex
from .model import ROOT, atomic_json, day, merge_records, week_start


def read_records(directory):
    result=[]
    for file in sorted((Path(directory)/'records').glob('*.jsonl')):
        result.extend(json.loads(line) for line in file.read_text().splitlines() if line.strip())
    return result


def save_records(directory,records):
    directory=Path(directory)/'records';directory.mkdir(parents=True,exist_ok=True)
    partitions={}
    for r in records:partitions.setdefault(r['source'],[]).append(r)
    for source,rows in partitions.items():
        path=directory/(source+'.jsonl');tmp=path.with_suffix('.tmp')
        tmp.write_text(''.join(json.dumps(r,ensure_ascii=False,sort_keys=True)+'\n' for r in rows))
        tmp.replace(path)


def collect(args):
    now=datetime.now(timezone.utc)
    if args.as_of:now=datetime.fromisoformat(args.as_of.replace('Z','+00:00'))
    stamp=now.isoformat();run_id=now.strftime('%Y%m%dT%H%M%SZ')
    directory=Path(args.data_dir);directory.mkdir(parents=True,exist_ok=True)
    state_file=directory/'state.json'
    previous=json.loads(state_file.read_text()) if state_file.exists() else {}
    initial=not previous.get('last_success')
    baseline=week_start(day(stamp))-timedelta(weeks=args.weeks)
    sources=json.loads((ROOT/'config/sources.json').read_text())
    if args.sources:
        chosen=set(args.sources.split(','))
        for s in sources:s['enabled']=s['enabled'] and s['id'] in chosen
    old=read_records(directory)
    fetcher=Fetcher(ROOT/'.cache'/run_id)
    outcomes={};incoming=[]
    def run(source):
        sid=source['id'];old_state=previous.get('sources',{}).get(sid,{})
        # A newly enabled source receives the full backfill even in an established project.
        start=baseline if not old_state.get('last_success') else day(old_state['last_success'])-timedelta(days=14)
        if day(stamp).day<=7:start=min(start,baseline)
        try:
            rows=ADAPTERS[source['adapter']](source,start,stamp,fetcher,initial=not old_state.get('last_success'))
            # Keep all conference/report entries; require a topic match for physics/journal results.
            filtered=[r for r in rows if r['kind'] in {'talk','report'} or r['topics']]
            return sid,filtered,dict(status='success',fetched=len(rows),included=len(filtered),last_success=stamp,
                    covered_from=min(old_state.get('covered_from',start.isoformat()),start.isoformat()),
                    message='Completed',query_from=start.isoformat())
        except Exception as e:
            # Error strings from adapters are sanitized and never contain authentication headers.
            return sid,[],dict(status='failed',fetched=0,included=0,last_success=old_state.get('last_success'),
                  covered_from=old_state.get('covered_from'),message=str(e)[:220])
    enabled=[s for s in sources if s['enabled'] and s['adapter'] in ADAPTERS]
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures={pool.submit(run,s):s for s in enabled}
        for future in as_completed(futures):
            sid,rows,status=future.result();outcomes[sid]=status;incoming.extend(rows)
            print(f'{sid}: {status["status"]} ({len(rows)} included)',flush=True)
    for s in sources:
        if not s['enabled']:outcomes[s['id']]={'status':'disabled','message':'Disabled in configuration.','fetched':0}
    fatal=[s['id'] for s in sources if s['enabled'] and s['required'] and outcomes.get(s['id'],{}).get('status')!='success']
    if fatal:
        atomic_json(directory/'last-attempt.json',dict(run_id=run_id,attempted_at=stamp,status='failed',sources=outcomes))
        print('Required sources failed; published records and successful checkpoints were preserved.',file=sys.stderr)
        return 1
    overrides=json.loads((ROOT/'config/overrides.json').read_text())
    records=merge_records(old,incoming,overrides)
    for source in sources:
        if source['adapter']=='openalex' and source['enabled']:
            try:records,outcomes[source['id']]=enrich_openalex(records,source,stamp,fetcher)
            except Exception:
                outcomes[source['id']]={'status':'failed','message':'Metadata enrichment failed; bibliographic records preserved.','fetched':0}
    if not records:
        raise ValueError('No records collected; refusing to create an empty publication')
    digest=hashlib.sha256(json.dumps(records,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    state=dict(schema_version=1,run_id=run_id,last_success=stamp,sources=outcomes,
               record_count=len(records),content_hash=digest,code_sha=os.environ.get('GITHUB_SHA','local'),
               baseline=baseline.isoformat(),initial_backfill=initial,
               status='partial' if any(v['status']=='failed' for v in outcomes.values()) else 'success')
    save_records(directory,records)
    atomic_json(state_file,state)
    atomic_json(directory/'runs'/f'{run_id}.json',state)
    atomic_json(directory/'last-attempt.json',dict(state,attempted_at=stamp))
    print(f'Saved {len(records)} records. Run: {run_id}',flush=True)
    return 0


def main():
    p=argparse.ArgumentParser(description='Collect and normalize quantum research metadata.')
    p.add_argument('--data-dir',default=str(ROOT/'data'))
    p.add_argument('--weeks',type=int,default=12)
    p.add_argument('--sources',help='Comma-separated source IDs, for source validation only')
    p.add_argument('--as-of',help='ISO timestamp for reproducible test runs')
    args=p.parse_args()
    if not 1<=args.weeks<=104:p.error('--weeks must be between 1 and 104')
    sys.exit(collect(args))


if __name__=='__main__':main()
