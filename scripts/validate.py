"""Validate the static artifact before upload, including cross-file data identity."""
import argparse
import json
import re
import sys
from pathlib import Path
from html.parser import HTMLParser

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from pipeline.content import load_articles,load_site_config
from pipeline.render import article_path


class Assets(HTMLParser):
    def __init__(self):super().__init__();self.paths=[]
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        value=attrs.get('src') or (attrs.get('href') if tag=='link' else None)
        if value and value.startswith('/'):self.paths.append(value)


def validate(directory,production=False):
    root=Path(directory)
    articles=load_articles();site=load_site_config()
    routes=['index.html','research/index.html','archive/index.html','methodology/index.html','analysis/index.html','guides/index.html',
            'about/index.html','contact/index.html','editorial-policy/index.html','privacy/index.html','terms/index.html','404.html','_headers','robots.txt','sitemap.xml']
    routes += [article_path(article).strip('/')+'/index.html' for article in articles]
    for path in routes:
        assert (root/path).is_file(),f'Missing {path}'
    parser=Assets();parser.feed((root/'index.html').read_text(encoding='utf-8'))
    for path in parser.paths:assert (root/path.lstrip('/')).is_file(),f'Missing asset {path}'
    summary=json.loads((root/'data/summary.json').read_text(encoding='utf-8'));index=json.loads((root/'data/index.json').read_text(encoding='utf-8'));manifest=json.loads((root/'data/manifest.json').read_text(encoding='utf-8'))
    assert summary['run_id']==index['run_id']==manifest['run_id'],'Mixed data snapshots'
    assert summary['build_id']==index['build_id']==manifest['build_id'],'Mixed application builds'
    if production:assert manifest['snapshot_type']=='live','Fixture data must never be deployed'
    editorial=json.loads((root/'data/editorial.json').read_text(encoding='utf-8'))
    assert editorial['build_id']==manifest['build_id'],'Editorial index differs from application build'
    assert len(editorial['articles'])==len(articles),'Editorial index is incomplete'
    ids={r['id'] for r in index['records']}
    assert len(ids)==len(index['records']),'Duplicate record identifiers'
    assert len(ids)==summary['totals']['records'],'Index count differs from totals'
    for r in index['records']:
        assert (root/r['detail_shard'].lstrip('/')).is_file(),'Missing detail shard'
        assert set(r['linked_record_ids'])<=ids,'Dangling linked record'
    for shard in (root/'data/details').glob('*.json'):
        for key,record in json.loads(shard.read_text(encoding='utf-8')).items():assert key==record['id'] and key in ids
    html_routes=[path for path in routes if path.endswith('.html') and path!='404.html']
    titles=set();sitemap=(root/'sitemap.xml').read_text(encoding='utf-8')
    for relative in html_routes:
        document=(root/relative).read_text(encoding='utf-8')
        assert '<h1' in document,f'Missing page heading: {relative}'
        assert 'Loading research' not in document,f'Loading-only document: {relative}'
        title=re.search(r'<title>(.*?)</title>',document,re.S)
        canonical=re.search(r'<link rel="canonical" href="([^"]+)"',document)
        assert title and title.group(1) not in titles,f'Missing or duplicate title: {relative}'
        titles.add(title.group(1));assert canonical,f'Missing canonical: {relative}'
        assert canonical.group(1) in sitemap,f'Canonical missing from sitemap: {relative}'
    robots=(root/'robots.txt').read_text(encoding='utf-8')
    assert 'User-agent: *' in robots and site['canonical_origin']+'/sitemap.xml' in robots,'Invalid robots.txt'
    verification_file=site['search_console_verification_file']
    expected_verification=f'google-site-verification: {verification_file}'
    assert (root/verification_file).read_text(encoding='utf-8').strip()==expected_verification,'Invalid Search Console verification file'
    ad_code_absent=all('adsbygoogle' not in path.read_text(encoding='utf-8',errors='ignore') for path in root.rglob('*') if path.is_file())
    if site['ads']['mode']=='off':
        assert not (root/'ads.txt').exists(),'ads.txt must not contain an invented publisher ID'
        assert ad_code_absent,'Advertising code present while ads are off'
    else:
        assert (root/'ads.txt').read_text(encoding='utf-8').strip()==site['ads']['ads_txt'],'ads.txt does not match the reviewed publisher record'
        if site['ads']['mode']=='verification':assert ad_code_absent,'Ad code must stay off during publisher verification'
    files=[p for p in root.rglob('*') if p.is_file()]
    assert len(files)<20000,'Split or migrate data before the Pages asset limit'
    assert max(p.stat().st_size for p in files)<25*1024*1024,'Oversized Pages asset'
    print(f'Validated {len(files)} files, {len(ids)} records, {len(articles)} articles, matching run {summary["run_id"]}')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('directory',nargs='?',default='dist');p.add_argument('--production',action='store_true');a=p.parse_args();validate(a.directory,a.production)
