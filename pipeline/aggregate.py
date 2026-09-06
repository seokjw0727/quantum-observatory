from datetime import timedelta
from .model import TOPICS, day, group_works, week_start


def record_date(r):
    if r.get('event_start'):return r['event_start']
    return r.get('published_at') if r.get('date_precision')=='day' else None


def aggregate(records,state,overrides=None):
    works=group_works(records,(overrides or {}).get('merge',[]))
    now=day(state['last_success']);current=week_start(now)
    research_sources=[sid for sid in ['arxiv','crossref'] if state['sources'].get(sid,{}).get('status')!='disabled']
    def covered(start,end):
        return all(state['sources'].get(sid,{}).get('status')=='success' and
                   state['sources'][sid].get('covered_from') and
                   day(state['sources'][sid]['covered_from'])<=start for sid in research_sources) and end<=now and bool(research_sources)
    weeks=[]
    for i in range(12,-1,-1):
        start=current-timedelta(weeks=i);end=start+timedelta(days=7)
        papers=[w for w in works if w['is_research'] and w['first_published'] and start<=day(w['first_published'])<end]
        in_period=[r for r in records if record_date(r) and start<=day(record_date(r))<end]
        newly_seen=[r for r in records if start<=day(r['observed_at'])<end]
        counts={t:sum(t in w['topics'] for w in papers) for t in TOPICS}
        complete=covered(start,end)
        previous=weeks[-1] if weeks else None
        delta=(len(papers)-previous['research'])/previous['research']*100 if previous and previous['research'] and complete and previous['comparable'] else None
        weeks.append(dict(id=start.isoformat(),end=end.isoformat(),research=len(papers),
            talks=sum(r['kind']=='talk' for r in in_period),reports=sum(r['kind']=='report' for r in in_period),
            discovered=len(newly_seen),topics=counts,comparable=complete,change_pct=delta,
            status='in_progress' if end>now else ('backfilled' if complete else 'incomplete'),
            publications=sum(r['kind']=='journal_article' for r in in_period),
            revisions=sum(1 for r in records for e in r.get('events',[]) if e.get('type')=='revision' and e.get('date') and start<=day(e['date'])<end)))
    for i,w in enumerate(weeks):
        history=weeks[max(0,i-4):i]
        w['rising']=[]
        if len(history)==4 and w['comparable'] and all(p['comparable'] and p['research']>0 for p in history) and w['research']:
            for topic,n in w['topics'].items():
                if n<5:continue
                baseline=sum(p['topics'][topic]/p['research'] for p in history)/4
                pp=100*(n/w['research']-baseline)
                if pp>0:w['rising'].append({'topic':topic,'count':n,'change_pp':round(pp,2)})
            w['rising'].sort(key=lambda r:r['change_pp'],reverse=True)
    work_map={rid:w for w in works for rid in w['record_ids']}
    indexed=[]
    for r in records:
        w=work_map[r['id']]
        indexed.append(dict(id=r['id'],work_id=w['id'],title=r['title'],authors=r['authors'],kind=r['kind'],
            source=r['source'],topics=w['topics'] if r['kind'] in {'preprint','journal_article','conference_paper'} else r['topics'],date=record_date(r),date_precision=r.get('date_precision','day'),
            event_end=r.get('event_end'),url=r['url'],venue=r.get('venue'),doi=r.get('doi'),arxiv_id=r.get('arxiv_id'),
            first_published=w['first_published'],observed_at=r['observed_at'],
            abstract=r.get('abstract'),presentation_status=r.get('presentation_status'),
            citations=(r.get('enrichment') or {}).get('citations',r.get('citations')),
            citations_as_of=(r.get('enrichment') or {}).get('as_of',r.get('citations_as_of')),
            linked_record_ids=w['record_ids'],version=r.get('version'),events=r.get('events',[]),
            provenance=r.get('provenance',{})))
    indexed.sort(key=lambda r:(r['date'] or '',r['id']),reverse=True)
    return {'schema_version':1,'run_id':state['run_id'],'generated_at':state['last_success'],
        'last_complete_week':(current-timedelta(days=7)).isoformat(),'topics':TOPICS,'weeks':weeks,
        'totals':{'records':len(records),'research':sum(w['is_research'] for w in works),
                  'talks':sum(r['kind']=='talk' for r in records),'reports':sum(r['kind']=='report' for r in records),
                  'undated':sum(not record_date(r) for r in records)},'records':indexed}
