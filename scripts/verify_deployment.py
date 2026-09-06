"""Require the public deployment to serve exactly the built collection run."""
import json
import os
import time
import urllib.request
from urllib.parse import urlparse

url=os.environ['SITE_URL'].rstrip('/')
if urlparse(url).scheme!='https':raise ValueError('SITE_URL must use HTTPS')
expected=json.load(open('dist/data/manifest.json'))['build_id']
headers={'Cache-Control':'no-cache','User-Agent':'QuantumObservatory/0.1 (deployment verification)'}
for attempt in range(6):
    try:
        req=urllib.request.Request(url+'/data/manifest.json?run='+expected,headers=headers)
        with urllib.request.urlopen(req,timeout=20) as response:actual=json.load(response)['build_id']
        if actual==expected:
            print('Deployment verified: '+expected);break
    except (OSError,ValueError,KeyError):pass
    if attempt==5:raise RuntimeError('Deployment has not served the expected snapshot; inspect Pages before retrying')
    time.sleep(10)

checks={
    '/':'Research overview',
    '/analysis/':'Research analysis',
    '/guides/':'Research reading guides',
    '/methodology/':'Sources &amp; methodology',
    '/privacy/':'Privacy policy',
    '/sitemap.xml':'https://qobservatory.com/analysis/',
    '/robots.txt':'Sitemap: https://qobservatory.com/sitemap.xml',
}
for path,marker in checks.items():
    request=urllib.request.Request(url+path+'?build='+expected,headers=headers)
    with urllib.request.urlopen(request,timeout=20) as response:
        body=response.read().decode('utf-8')
        if response.status!=200 or marker not in body:
            raise RuntimeError('Deployment route verification failed: '+path)
print(f'Content routes verified: {len(checks)}')
