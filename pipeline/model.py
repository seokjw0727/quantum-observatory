import hashlib
import html
import json
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import unquote, urlparse

ROOT = Path(__file__).resolve().parents[1]
KST = timezone(timedelta(hours=9))
TOPICS = json.loads((ROOT / 'config/topics.json').read_text(encoding='utf-8'))
KINDS = {'preprint', 'journal_article', 'conference_paper', 'talk', 'report'}


def clean(text):
    # Strip known metadata markup, never arbitrary angle-bracket mathematics.
    tags=r'</?(?:(?:jats|mml):)?(?:p|i|b|em|strong|sup|sub|span|br|title|italic|bold|math|mi|mn|mo|mrow)(?:\s+[^<>]*)?\s*/?>'
    return ' '.join(html.unescape(re.sub(tags, ' ', text or '',flags=re.I)).split())


def doi_id(value):
    value = unquote((value or '').strip()).lower()
    value = re.sub(r'^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)', '', value)
    return value.rstrip(' .') if re.match(r'^10\.\d{4,9}/\S+$', value) else None


def arxiv_id(value):
    value = re.sub(r'^https?://(?:www\.)?arxiv\.org/(?:abs|pdf)/', '', (value or '').strip())
    value = re.sub(r'\.pdf$', '', value)
    value = re.sub(r'v\d+$', '', value)
    return value if re.fullmatch(r'(?:\d{4}\.\d{4,5}|[a-z-]+/\d{7})', value) else None


def safe_url(value):
    p = urlparse(value or '')
    return value if p.scheme in {'http', 'https'} and p.hostname and not p.username else None


def day(value):
    if not value:
        return None
    if 'T' in value:
        return datetime.fromisoformat(value.replace('Z', '+00:00')).astimezone(KST).date()
    return date.fromisoformat(value)


def week_start(value):
    d = value if isinstance(value, date) else day(value)
    return d - timedelta(days=d.weekday())


def identify(source, source_id):
    return source + ':' + hashlib.sha256(source_id.encode()).hexdigest()[:20]


def classify(title, abstract=''):
    text = clean(title + ' ' + abstract).lower()
    evidence = {key: [p for p in value['patterns'] if p in text] for key, value in TOPICS.items()}
    return [key for key, matches in evidence.items() if matches], {k:v for k,v in evidence.items() if v}


def validate(record):
    for key in ['id','source','source_id','title','kind','url','observed_at']:
        if not record.get(key):
            raise ValueError('Missing record field: ' + key)
    if record['kind'] not in KINDS or not safe_url(record['url']):
        raise ValueError('Invalid record kind or URL')
    for key in ['published_at','updated_at','event_start','event_end']:
        if record.get(key):
            day(record[key])
    if not isinstance(record.get('authors', []), list):
        raise ValueError('Authors must be an array')
    return record


def make_record(source, source_id, title, kind, url, observed_at, **fields):
    record = dict(id=identify(source, source_id), source=source, source_id=source_id,
                  title=clean(title), kind=kind, url=safe_url(url), observed_at=observed_at,
                  authors=[], abstract=None, published_at=None, date_precision='day', doi=None,
                  arxiv_id=None, venue=None, updated_at=None, events=[], provenance={})
    record.update(fields)
    record['doi'] = doi_id(record.get('doi'))
    record['arxiv_id'] = arxiv_id(record.get('arxiv_id'))
    record['topics'], record['classification_evidence'] = classify(record['title'], record.get('abstract') or '')
    record['classification_version'] = 'rules-v1'
    return validate(record)


def merge_records(old, incoming, overrides=None):
    merged = {r['id']: dict(r) for r in old}
    for record in incoming:
        record = dict(record)
        previous = merged.get(record['id'])
        if previous:
            record['observed_at'] = previous['observed_at']
            events = previous.get('events', []) + record.get('events', [])
            record['events'] = list({json.dumps(e,sort_keys=True):e for e in events}.values())
            for key in ['doi','arxiv_id','abstract','enrichment']:
                if not record.get(key) and previous.get(key):
                    record[key] = previous[key]
        merged[record['id']] = record
    for rid, changes in (overrides or {}).get('records', {}).items():
        if rid in merged:
            merged[rid].update(changes)
            validate(merged[rid])
    return sorted(merged.values(), key=lambda r:r['id'])


def group_works(records, forced_merges=()):
    parent = {r['id']:r['id'] for r in records}
    def root(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    def join(a,b):
        a,b=root(a),root(b)
        parent[max(a,b)] = min(a,b)
    identifiers = {}
    for r in records:
        # Talks and reports link to research, but never shift a paper's first-publication date.
        for key in ['doi','arxiv_id']:
            v = r.get(key)
            if v:
                token = key + ':' + v
                if token in identifiers:
                    join(r['id'],identifiers[token])
                identifiers[token]=r['id']
    for pair in forced_merges:
        if len(pair)==2 and all(x in parent for x in pair):
            join(*pair)
    groups={}
    for r in records:
        groups.setdefault(root(r['id']), []).append(r)
    result=[]
    for key, group in groups.items():
        papers=[r for r in group if r['kind'] in {'preprint','journal_article','conference_paper'}]
        dates=[r['published_at'] for r in papers if r.get('published_at') and r.get('date_precision')=='day']
        first=min(dates,key=day) if dates else None
        result.append(dict(id=key, record_ids=[r['id'] for r in group], first_published=first,
                           topics=sorted({t for r in group for t in r['topics']}),
                           sources=sorted({r['source'] for r in papers}), is_research=bool(papers)))
    return result


def atomic_json(path, value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix(path.suffix+'.tmp')
    tmp.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    tmp.replace(path)
