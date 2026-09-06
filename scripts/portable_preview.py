"""Bundle the same application and live snapshot into one offline-reviewable HTML file."""
import json
import re
from pathlib import Path

root=Path(__file__).resolve().parents[1]
dist=root/'dist'
template=(dist/'index.html').read_text(encoding='utf-8')
template=re.sub(r'\s*<link rel="icon"[^>]+>','',template)
css=(dist/'assets/style.css').read_text(encoding='utf-8')
template=re.sub(r'<link rel="stylesheet" href="/assets/style.css"\s*/?>',lambda m:'<style>'+css+'</style>',template)
parts=[]
for name in ['core.js','motion.js','selects.js','common.js','app.js']:
    source=(dist/'assets'/name).read_text(encoding='utf-8')
    source=re.sub(r'^import\s+(?:\{.*?\}\s+from\s+)?[\"\'][^\"\']+[\"\'];\s*','',source,flags=re.S|re.M)
    parts.append(re.sub(r'\bexport ', '',source))
core,app='\n'.join(parts[:-1]),parts[-1]
app=re.sub(r'const path\s*=\s*location\.pathname\.replace\([^;]+;',"const path=({overview:'',research:'/research',archive:'/archive',methodology:'/methodology'})[new URLSearchParams(location.search).get('view')||'overview'];",app)
app=app.replace('const p = new URLSearchParams();',"const p = new URLSearchParams(); p.set('view',page);")
app=app.replace('await fetch(', 'await resourceFetch(')
payload={'/'+str(file.relative_to(dist)).replace('\\','/'):json.loads(file.read_text(encoding='utf-8')) for file in (dist/'data').rglob('*.json')}
data=json.dumps(payload,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c')
loader="""
const offlineData=JSON.parse(document.querySelector('#snapshot-data').textContent);
async function resourceFetch(url){const body=offlineData[url.split('?')[0]];return {ok:body!==undefined,json:async()=>body};}
document.addEventListener('click',e=>{
  const link=e.target.closest('a');if(!link)return;
  const href=link.getAttribute('href');if(!href||!href.startsWith('/'))return;
  e.preventDefault();
  if(href.startsWith('/data/')){
    const body=offlineData[href];if(body){const url=URL.createObjectURL(new Blob([JSON.stringify(body,null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download=href.split('/').pop();a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}return;
  }
  const route=new URL(href,'https://preview.invalid');const view=({'/':'overview','/research/':'research','/archive/':'archive','/methodology/':'methodology'})[route.pathname]||'overview';
  const next=new URLSearchParams(route.search);next.set('view',view);location.search=next.toString();
});
"""
template=re.sub(r'<script type="module" src="/assets/app.js"></script>','',template)
script=(core+'\n'+loader+'\n'+app).replace('</script','<\\/script')
template=template.replace('</body>',f'<script type="application/json" id="snapshot-data">{data}</script>\n<script type="module">{script}</script>\n</body>')
out=root/'deliverables';out.mkdir(exist_ok=True)
target=out/'quantum-observatory-preview.html';target.write_text(template,encoding='utf-8')
print(f'Created portable preview: {target} ({target.stat().st_size:,} bytes)')
