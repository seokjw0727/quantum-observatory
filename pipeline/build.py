import argparse
import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path
from xml.sax.saxutils import escape as xml_escape

from .aggregate import aggregate
from .collect import read_records
from .content import load_articles, load_site_config
from .model import ROOT, atomic_json, merge_records
from .render import article_path, page_heading, render_article, render_dynamic, render_listing, render_policy_page, shell, write_page


def build(data_dir,output):
    data_dir=Path(data_dir);output=Path(output)
    if output.resolve() in {ROOT.resolve(),data_dir.resolve()}:
        raise ValueError('Build output must not replace source or input data')
    if not (data_dir/'state.json').exists():
        raise ValueError('No successful snapshot. Run python -m pipeline.collect first.')
    state=json.loads((data_dir/'state.json').read_text(encoding='utf-8'))
    overrides=json.loads((ROOT/'config/overrides.json').read_text(encoding='utf-8'))
    records=merge_records(read_records(data_dir),[],overrides)
    result=aggregate(records,state,overrides)
    site_config=load_site_config();articles=load_articles()
    fingerprint=hashlib.sha256(state['content_hash'].encode())
    for folder in ['web','config','pipeline','content']:
        for file in sorted((ROOT/folder).rglob('*')):
            if file.is_file() and '__pycache__' not in file.parts and file.suffix!='.pyc':
                fingerprint.update(str(file.relative_to(ROOT)).encode());fingerprint.update(file.read_bytes())
    build_id=fingerprint.hexdigest()[:24]
    result['build_id']=build_id
    # Every generated page carries the build fingerprint into mutable asset and
    # data URLs so a new deployment cannot be paired with a stale browser cache.
    site_config=dict(site_config,_build_id=build_id)
    try:
        build_code_sha=os.environ.get('GITHUB_SHA') or subprocess.check_output(
            ['git','rev-parse','HEAD'],cwd=ROOT,text=True,stderr=subprocess.DEVNULL).strip()
    except (OSError,subprocess.CalledProcessError):
        build_code_sha=state['code_sha']
    # Build in a staging directory so incomplete builds cannot replace the previous output.
    stage=output.with_name(output.name+'-staging')
    if stage.exists():shutil.rmtree(stage)
    shutil.copytree(ROOT/'web',stage)
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
    source_config=json.loads((ROOT/'config/sources.json').read_text(encoding='utf-8'))
    sources=[]
    for s in source_config:
        status=state['sources'].get(s['id'],{'status':'not_configured','message':'Not collected yet.'})
        if not s['enabled']:
            status={'status':'disabled','message':s.get('note','Automated collection is disabled.'),'fetched':0}
        entry={k:v for k,v in s.items() if k in {'id','name','kind','url','required','enabled','note'}}
        entry.update(status);sources.append(entry)
    manifest=dict(schema_version=1,run_id=state['run_id'],build_id=build_id,generated_at=state['last_success'],
        content_hash=state['content_hash'],code_sha=build_code_sha,collection_code_sha=state['code_sha'],sources=sources,
        snapshot_type=state.get('snapshot_type','live'),status=state['status'])
    atomic_json(stage/'data/manifest.json',manifest)
    editorial_index=[{key:article[key] for key in ['slug','type','title','description','summary','author','published_at','updated_at']} | {'path':article_path(article)} for article in articles]
    atomic_json(stage/'data/editorial.json',{'schema_version':1,'build_id':build_id,'articles':editorial_index})
    for page in ['overview','research','archive','methodology']:
        write_page(stage,'' if page=='overview' else page,render_dynamic(site_config,page,result,index,manifest,articles))
    for kind in ['analysis','guide']:
        route='analysis' if kind=='analysis' else 'guides'
        write_page(stage,route,render_listing(site_config,articles,kind))
    for article in articles:
        related=[candidate for candidate in articles if candidate['slug']!=article['slug'] and (candidate['type']==article['type'] or candidate['type']=='guide')]
        write_page(stage,article_path(article).strip('/'),render_article(site_config,article,related))
    for route in ['about','contact','editorial-policy','privacy','terms']:
        write_page(stage,route,render_policy_page(site_config,route))
    not_found=page_heading('Page not found','The requested page does not exist or may have moved.',eyebrow='QUANTUM OBSERVATORY')+'<p class="policy-copy"><a href="/">Return to the research overview</a> or <a href="/research/">browse the research library</a>.</p>'
    (stage/'404.html').write_text(shell(site_config,title='Page not found',description='The requested Quantum Observatory page could not be found.',body=not_found,active='',path='/404.html',robots='noindex,follow'),encoding='utf-8')
    public_paths=['/','/research/','/archive/','/methodology/','/analysis/','/guides/','/about/','/contact/','/editorial-policy/','/privacy/','/terms/']+[article_path(article) for article in articles]
    lastmod=max(article['updated_at'] for article in articles)
    sitemap='<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'+''.join(f'<url><loc>{xml_escape(site_config["canonical_origin"].rstrip("/")+path)}</loc><lastmod>{lastmod}</lastmod></url>\n' for path in public_paths)+'</urlset>\n'
    (stage/'sitemap.xml').write_text(sitemap,encoding='utf-8')
    (stage/'robots.txt').write_text(f'User-agent: *\nAllow: /\n\nSitemap: {site_config["canonical_origin"].rstrip("/")}/sitemap.xml\n',encoding='utf-8')
    if site_config['ads']['mode'] != 'off':
        (stage/'ads.txt').write_text(site_config['ads']['ads_txt']+'\n',encoding='utf-8')
    if output.exists():shutil.rmtree(output)
    stage.replace(output)
    print(f'Built {len(index)} records, {len(shards)} detail shards, {len(public_paths)} public routes → {output}')


def main():
    p=argparse.ArgumentParser();p.add_argument('--data-dir',default=str(ROOT/'data'));p.add_argument('--output',default=str(ROOT/'dist'))
    a=p.parse_args();build(a.data_dir,a.output)


if __name__=='__main__':main()
