"""Source adapters. Network failures and incomplete pagination are never treated as zero results."""
import hashlib
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path

from .model import ROOT, arxiv_id, clean, day, doi_id, make_record, safe_url


class Fetcher:
    def __init__(self, cache_dir=None, timeout=45):
        self.cache_dir = Path(cache_dir or ROOT / '.cache/http')
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.timeout = timeout
        self.last_request = {}

    def get(self, url, params=None, headers=None):
        if params:
            url += ('&' if '?' in url else '?') + urllib.parse.urlencode(params)
        if not safe_url(url):
            raise ValueError('Unsupported source URL')
        host = urllib.parse.urlparse(url).hostname
        interval = 3.1 if 'arxiv.org' in host else 0.25
        # Cache is scoped to one collection run; it is never a durable checkpoint.
        target = self.cache_dir / hashlib.sha256(url.encode()).hexdigest()
        if target.exists():
            return target.read_bytes()
        contact = os.environ.get('CONTACT_EMAIL', '')
        request_headers = {'User-Agent': 'QuantumObservatory/0.1' + (f' (mailto:{contact})' if contact else '')}
        request_headers.update(headers or {})
        for attempt in range(3):
            time.sleep(max(0, interval - (time.monotonic() - self.last_request.get(host, 0))))
            try:
                self.last_request[host] = time.monotonic()
                req = urllib.request.Request(url, headers=request_headers)
                with urllib.request.urlopen(req, timeout=self.timeout) as response:
                    body = response.read(25 * 1024 * 1024 + 1)
                if len(body) > 25 * 1024 * 1024:
                    raise ValueError('Source response exceeds 25 MiB')
                target.write_bytes(body)
                return body
            except urllib.error.HTTPError as e:
                if e.code not in {429, 500, 502, 503, 504} or attempt == 2:
                    raise RuntimeError(f'{host}: HTTP {e.code}') from None
                delay = e.headers.get('Retry-After', '')
                time.sleep(min(30, int(delay) if delay.isdigit() else 2 ** (attempt + 1)))
            except (urllib.error.URLError, TimeoutError, OSError):
                if attempt == 2:
                    raise RuntimeError(f'{host}: request timed out or connection failed') from None
                time.sleep(2 ** (attempt + 1))


ATOM = {'a':'http://www.w3.org/2005/Atom','x':'http://arxiv.org/schemas/atom',
        'o':'http://a9.com/-/spec/opensearch/1.1/'}


def parse_arxiv(body, now):
    feed=ET.fromstring(body)
    total=feed.findtext('o:totalResults',namespaces=ATOM)
    if total is None:
        raise ValueError('arXiv response missing totalResults')
    records=[]
    for e in feed.findall('a:entry',ATOM):
        text=lambda key: e.findtext(key,default='',namespaces=ATOM)
        aid=arxiv_id(text('a:id'))
        if not aid:
            raise ValueError('Unexpected arXiv entry identifier')
        version=re.search(r'v(\d+)$',text('a:id'))
        version=int(version.group(1)) if version else 1
        records.append(make_record('arxiv',aid,text('a:title'),'preprint','https://arxiv.org/abs/'+aid,now,
            authors=[a.findtext('a:name',default='',namespaces=ATOM) for a in e.findall('a:author',ATOM)],
            abstract=clean(text('a:summary')),published_at=text('a:published'),updated_at=text('a:updated'),
            arxiv_id=aid,doi=text('x:doi'),venue='arXiv',version=version,
            categories=[c.attrib['term'] for c in e.findall('a:category',ATOM)],
            events=[{'type':'revision','date':text('a:updated'),'version':version}] if version>1 else [],
            provenance={'method':'arxiv-atom','retrieved_at':now}))
    return records,int(total)


def collect_arxiv(source, start, now, fetcher, initial=False):
    result=[];size=source.get('page_size',1000)
    for page in range(source.get('max_pages',30)):
        query=source.get('query','cat:quant-ph')
        body=fetcher.get('https://export.arxiv.org/api/query',dict(search_query=query,start=page*size,
                         max_results=size,sortBy='lastUpdatedDate',sortOrder='descending'))
        rows,total=parse_arxiv(body,now)
        if not rows and page*size<total:
            raise ValueError('arXiv returned an empty page before completion')
        result.extend(r for r in rows if day(r['updated_at'])>=start)
        if page*size+len(rows)>=total or (rows and day(rows[-1]['updated_at'])<start):
            return result
    raise ValueError('arXiv page limit reached; increase max_pages before advancing the checkpoint')


def crossref_date(item):
    for key in ['published-online','published-print','published','issued']:
        parts=item.get(key,{}).get('date-parts',[[]])[0]
        if parts and parts[0]>1900:
            return '-'.join(str(x).zfill(4 if i==0 else 2) for i,x in enumerate(parts)), ['year','month','day'][min(3,len(parts))-1]
    return None,'unknown'


def parse_crossref(items, now):
    result=[]
    for item in items:
        doi=doi_id(item.get('DOI'))
        if not doi or not item.get('title'):
            raise ValueError('Crossref work missing DOI or title')
        published,precision=crossref_date(item)
        links=[]
        for rel in item.get('relation',{}).values():
            links.extend(v.get('id','') for v in rel)
        aid=next((arxiv_id(v) for v in links if arxiv_id(v)),None)
        # Crossref abstracts may carry publisher rights; retain links and metadata only.
        r=make_record('crossref',doi,item['title'][0],'journal_article','https://doi.org/'+doi,now,
            authors=[clean(a.get('given','')+' '+a.get('family','')) for a in item.get('author',[])],
            published_at=published if precision=='day' else None,published_label=published,date_precision=precision,
            updated_at=item.get('indexed',{}).get('date-time'),doi=doi,arxiv_id=aid,
            venue=(item.get('container-title') or ['Journal'])[0],
            citations=item.get('is-referenced-by-count'),citations_as_of=now,
            events=[{'type':'journal_publication','date':published}] if precision=='day' else [],
            provenance={'method':'crossref-rest','retrieved_at':now})
        result.append(r)
    return result


def collect_crossref(source,start,now,fetcher,initial=False):
    result=[]
    for issn in source['issns']:
        cursor='*';seen=set()
        for page in range(source.get('max_pages',30)):
            date_filter='from-pub-date' if initial else 'from-index-date'
            params={'filter':f'{date_filter}:{start.isoformat()}','rows':source.get('page_size',500),'cursor':cursor}
            if os.environ.get('CONTACT_EMAIL'):params['mailto']=os.environ['CONTACT_EMAIL']
            payload=json.loads(fetcher.get('https://api.crossref.org/journals/'+issn+'/works',params))
            message=payload['message'];items=message['items']
            if not items:break
            # Crossref cursor tokens may stay unchanged across pages. Detect repeated content instead.
            fingerprint=hashlib.sha256(json.dumps([x.get('DOI') for x in items]).encode()).hexdigest()
            if fingerprint in seen:raise ValueError('Crossref repeated a page')
            seen.add(fingerprint)
            result.extend(parse_crossref(items,now))
            if len(items)<params['rows']:break
            cursor=message.get('next-cursor')
            if not cursor:raise ValueError('Crossref omitted pagination cursor')
        else:raise ValueError('Crossref page limit reached')
    return result


class Node:
    def __init__(self,tag='',attrs=(),parent=None):
        self.tag=tag;self.attrs=dict(attrs);self.parent=parent;self.children=[]
    def text(self):
        return clean(' '.join(x.text() if isinstance(x,Node) else x for x in self.children))
    def all(self,tag):
        for c in self.children:
            if isinstance(c,Node):
                if c.tag==tag:yield c
                yield from c.all(tag)


class Document(HTMLParser):
    def __init__(self,text):
        super().__init__(convert_charrefs=True);self.root=Node();self.stack=[self.root];self.feed(text)
    def handle_starttag(self,tag,attrs):
        node=Node(tag,attrs,self.stack[-1]);self.stack[-1].children.append(node)
        if tag not in {'meta','link','img','br','hr','input','source','wbr','area','embed','param','col','base'}:self.stack.append(node)
    def handle_endtag(self,tag):
        for i in range(len(self.stack)-1,0,-1):
            if self.stack[i].tag==tag:
                self.stack=self.stack[:i];break
    def handle_data(self,data):self.stack[-1].children.append(data)


def parse_qip(body,source,now):
    document=Document(body.decode('utf-8')).root;result=[]
    for li in document.all('li'):
        if list(li.all('li')):continue
        titles=list(li.all('u'))
        if not titles:continue
        title=clean(' '.join(x.text() for x in titles)).rstrip(': ')
        if len(title)<10:continue
        whole=li.text();tail=whole[len(title):].lstrip(': ')
        authors=[clean(x) for x in re.sub(r'\[.*?\]','',tail).split(',') if clean(x)]
        sid=hashlib.sha256(title.lower().encode()).hexdigest()[:20]
        result.append(make_record(source['id'],sid,title,'talk',source['url'],now,authors=authors,
            venue=source['venue'],event_start=source['event_start'],event_end=source['event_end'],
            date_precision='range',presentation_status='accepted',
            provenance={'method':'qip-underlined-titles-v1','retrieved_at':now}))
    if len(result)<3:raise ValueError('QIP page structure changed or no accepted talks found')
    return result


def collect_qip(source,start,now,fetcher,initial=False):
    return parse_qip(fetcher.get(source['url']),source,now)


def parse_reports(body,source,now):
    document=Document(body.decode('utf-8')).root;result={}
    for a in document.all('a'):
        url=urllib.parse.urljoin(source['url'],a.attrs.get('href',''))
        title=a.text()
        if not safe_url(url) or not re.search(r'\.pdf(?:$|[?#])',url,re.I) or len(title)<16:continue
        if not re.search(r'quantum|qis|nqi', title+' '+url,re.I):continue
        # Upload paths and document filenames are not reliable publication dates.
        r=make_record(source['id'],url,title,'report',url,now,venue=source['name'],date_precision='unknown',
                      provenance={'method':'official-pdf-index-v1','index_url':source['url'],'retrieved_at':now})
        result[r['id']]=r
    if not result:raise ValueError('Report index structure changed or no report links found')
    return list(result.values())


def collect_reports(source,start,now,fetcher,initial=False):
    return parse_reports(fetcher.get(source['url']),source,now)


def parse_gao(body,source,now):
    document=Document(body.decode('utf-8')).root
    headings=list(document.all('h1'))
    text=document.text();published=re.search(r'Published:\s*([A-Z][a-z]{2}\s+\d{1,2},\s*\d{4})',text)
    if not headings or not published:raise ValueError('GAO title/publication date missing')
    return [make_record(source['id'],source['url'],headings[0].text(),'report',source['url'],now,
             authors=['U.S. Government Accountability Office'],venue='U.S. GAO',
             published_at=datetime.strptime(published.group(1),'%b %d, %Y').date().isoformat(),
             provenance={'method':'gao-report-page-v1','retrieved_at':now})]


def collect_gao(source,start,now,fetcher,initial=False):
    return parse_gao(fetcher.get(source['url']),source,now)


def parse_osti(items,now):
    result=[]
    for item in items:
        if item.get('product_type')!='Technical Report':continue
        sid=str(item.get('osti_id',''))
        if not sid or not item.get('title'):raise ValueError('OSTI report missing identifier or title')
        r=make_record('osti',sid,item['title'],'report','https://www.osti.gov/biblio/'+sid,now,
            authors=[clean(re.sub(r'\[.*?\]','',a)) for a in item.get('authors',[])],
            # This field is a calendar publication date, despite its midnight timestamp format.
            published_at=(item.get('publication_date') or '')[:10] or None,
            doi=item.get('doi'),venue='DOE OSTI',
            provenance={'method':'osti-api-v1','retrieved_at':now})
        if r['topics']:result.append(r)
    return result


def collect_osti(source,start,now,fetcher,initial=False):
    result=[];seen=set()
    for page in range(1,source.get('max_pages',100)+1):
        params={'search':source.get('query','quantum'),'rows':source.get('page_size',100),'page':page,
                'publication_date_start' if initial else 'entry_date_start':start.strftime('%m/%d/%Y')}
        items=json.loads(fetcher.get('https://www.osti.gov/api/v1/records',params))
        if not isinstance(items,list):raise ValueError('Unexpected OSTI API response')
        if not items:return result
        fingerprint=hashlib.sha256(json.dumps([x.get('osti_id') for x in items]).encode()).hexdigest()
        if fingerprint in seen:raise ValueError('OSTI repeated a page; refusing to advance checkpoint')
        seen.add(fingerprint);result.extend(parse_osti(items,now))
        if len(items)<params['rows']:return result
    raise ValueError('OSTI page limit reached')


def enrich_openalex(records,source,now,fetcher):
    key=os.environ.get('OPENALEX_API_KEY')
    if not key:return records,{'status':'not_configured','message':'API key has not been configured.','fetched':0}
    eligible=[r for r in records if r.get('doi') and not r.get('enrichment')][:source.get('max_enrichment',100)]
    by_doi={}
    for i in range(0,len(eligible),25):
        batch=eligible[i:i+25]
        params={'filter':'doi:'+'|'.join('https://doi.org/'+r['doi'] for r in batch),'per-page':25}
        data=json.loads(fetcher.get('https://api.openalex.org/works',params,{'Authorization':'Bearer '+key}))
        for work in data['results']:
            by_doi[doi_id(work.get('doi'))]={'openalex_id':work['id'],'citations':work.get('cited_by_count'),
                'as_of':now,'institutions':sorted({v['display_name'] for a in work.get('authorships',[]) for v in a.get('institutions',[])})}
    for r in records:
        if r.get('doi') in by_doi:r['enrichment']=by_doi[r['doi']]
    return records,{'status':'success','message':'DOI metadata enrichment; bounded per-run budget.','fetched':len(by_doi),'last_success':now}


ADAPTERS={'arxiv':collect_arxiv,'crossref':collect_crossref,'qip':collect_qip,'reports':collect_reports,'gao':collect_gao,'osti':collect_osti}
