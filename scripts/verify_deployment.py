"""Require the public deployment to serve exactly the built collection run."""
import json
import os
import time
import urllib.request
from urllib.parse import urlparse

url=os.environ['SITE_URL'].rstrip('/')
if urlparse(url).scheme!='https':raise ValueError('SITE_URL must use HTTPS')
expected=json.load(open('dist/data/manifest.json'))['build_id']
for attempt in range(6):
    try:
        req=urllib.request.Request(url+'/data/manifest.json?run='+expected,headers={
            'Cache-Control':'no-cache',
            'User-Agent':'QuantumObservatory/0.1 (deployment verification)',
        })
        with urllib.request.urlopen(req,timeout=20) as response:actual=json.load(response)['build_id']
        if actual==expected:
            print('Deployment verified: '+expected);break
    except (OSError,ValueError,KeyError):pass
    if attempt==5:raise RuntimeError('Deployment has not served the expected snapshot; inspect Pages before retrying')
    time.sleep(10)
