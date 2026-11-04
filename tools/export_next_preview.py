"""Build isolated, source-grounded inputs for the Next static preview."""
from html import escape, unescape
from html.parser import HTMLParser
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import sys
import tempfile
from contextlib import nullcontext
from urllib.parse import urljoin, urlsplit, unquote, parse_qsl, urlencode

ROOT = Path(__file__).resolve().parents[1]
LEGACY = 'http://127.0.0.1:8765/psy-stats/'
BASE = '/psy-stats'
MIGRATED = {'index.html': '/', 'paths.html': '/paths/', 'terms/variable.html': '/terms/variable/', 'terms/sem.html': '/terms/sem/'}
VOID = {'area','base','br','col','embed','hr','img','input','link','meta','param','source','track','wbr'}


class Node:
    def __init__(self, tag='', attrs=()):
        self.tag, self.attrs, self.children = tag, dict(attrs), []

    def find(self, predicate):
        out = [self] if predicate(self) else []
        for child in self.children:
            if isinstance(child, Node): out.extend(child.find(predicate))
        return out


class Tree(HTMLParser):
    def __init__(self, text):
        super().__init__(convert_charrefs=False)
        self.root = Node()
        self.stack = [self.root]
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        node = Node(tag, attrs)
        self.stack[-1].children.append(node)
        if tag not in VOID: self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in VOID: self.stack.pop()

    def handle_endtag(self, tag):
        for i in range(len(self.stack)-1, 0, -1):
            if self.stack[i].tag == tag:
                del self.stack[i:]
                break

    def handle_data(self, data): self.stack[-1].children.append(data)
    def handle_entityref(self, name): self.handle_data('&'+name+';')
    def handle_charref(self, name): self.handle_data('&#'+name+';')


def formula_fonts(main, css):
    """Collect text/font pairs from rendered KaTeX spans, not hidden MathML."""
    rules=[]
    for selectors, declarations in re.findall(r'([^{}]+)\{([^{}]*)\}', css):
        props=dict(re.findall(r'(font-family|font-style|font-weight):([^;]+)', declarations))
        if not props: continue
        for selector in selectors.split(','):
            selector=selector.strip()
            if re.fullmatch(r'\.katex (?:\.[\w-]+)+', selector):
                rules.append((set(re.findall(r'\.([\w-]+)', selector)) - {'katex'}, props))
    texts={}
    def visit(node, inherited):
        if isinstance(node, str):
            text=unescape(node)
            if text.strip():
                font=f'{inherited["font-style"]} {inherited["font-weight"]} 16px "{inherited["font-family"]}"'
                texts[font]=texts.get(font, '')+text
            return
        props=dict(inherited); classes=set(node.attrs.get('class','').split())
        for required, declaration in rules:
            if required <= classes: props.update(declaration)
        for child in node.children: visit(child, props)
    for formula in main.find(lambda n:'katex-html' in n.attrs.get('class','').split()):
        visit(formula, {'font-family':'KaTeX_Main','font-style':'normal','font-weight':'400'})
    return [{'font':font,'text':''.join(dict.fromkeys(text))} for font,text in texts.items()]


def resource_path(root, relative):
    base = Path(root).resolve()
    candidate = (base / unquote(relative)).resolve()
    if not candidate.is_relative_to(base): raise ValueError('Resource escapes build root: '+relative)
    if not candidate.is_file(): raise FileNotFoundError(candidate)
    return candidate


def site_relative(value, page):
    url = urlsplit(urljoin('https://preview.invalid/'+page, value))
    if url.netloc != 'preview.invalid': return None
    return url.path.lstrip('/'), ('?'+url.query if url.query else '') + ('#'+url.fragment if url.fragment else '')


def export_preview(output, *, source_root=None, scope='representative'):
    if source_root is not None:
        return export_versioned(output, Path(source_root), scope)
    sys.path.insert(0, str(ROOT/'site'))
    from sitegen.build import build_site
    output = Path(output).resolve()
    generated, public = output/'generated', output/'public'
    generated.mkdir(parents=True, exist_ok=True)
    public.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT/'site/assets/search.js', generated/'search.cjs')
    with tempfile.TemporaryDirectory(prefix='psy-next-source-') as temp:
        built = Path(temp)/'dist'
        report = build_site('preview', built)
        data = json.loads((built/'assets/data/site-data.js').read_text(encoding='utf-8').split('=',1)[1].strip().rstrip(';'))
        resources = {'assets/site.css','assets/favicon.svg','assets/favicon.ico','assets/vendor/katex/katex.min.css'}
        pages = {}
        trees = {}
        def url(value, page, attr):
            resolved = site_relative(value, page)
            if resolved is None: return value
            relative, suffix = resolved
            if value.startswith('#'): return value
            if relative.endswith('.html') or relative == '':
                target = MIGRATED.get(relative or 'index.html')
                return (BASE+target if target else LEGACY+relative)+suffix
            resources.add(relative)
            return BASE+'/'+relative+suffix
        def markup(node, page):
            if isinstance(node, str): return node
            if node.tag == 'script': return ''
            attrs = []
            for key, val in node.attrs.items():
                if key.startswith('on'): continue
                if val is None: attrs.append(key); continue
                if key in ('href','src'): val = url(val,page,key)
                if key == 'srcset':
                    parts=[]
                    for part in val.split(','):
                        fields=part.strip().split()
                        if fields: parts.append(' '.join([url(fields[0],page,key)]+fields[1:]))
                    val=', '.join(parts)
                attrs.append(key+'="'+escape(val,quote=True)+'"')
            start='<'+node.tag+(' '+' '.join(attrs) if attrs else '')+'>'
            return start + ('' if node.tag in VOID else ''.join(markup(c,page) for c in node.children)+'</'+node.tag+'>')
        for key, page in [('index','index.html'),('paths','paths.html'),('variable','terms/variable.html'),('sem','terms/sem.html')]:
            tree=Tree((built/page).read_text(encoding='utf-8'))
            trees[key]=tree
            main=tree.root.find(lambda n:n.tag=='main')[0]
            html=''.join(markup(c,page) for c in main.children)
            (generated/(key+'.html')).write_text(html,encoding='utf-8')
            term=next((t for t in data['search'] if t['id']==key),None)
            pages[key]={'file':key+'.html','topic':term['topic'] if term else 'foundations'}
        cards=trees['index'].root.find(lambda n:n.attrs.get('data-term') is not None or 'data-term' in n.attrs)
        by_id={n.attrs['data-id']:n for n in cards}
        terms=[]
        for term in data['search']:
            if term['id'] in by_id:
                node=by_id[term['id']]
                node.attrs.pop('hidden',None)
                terms.append({**{k:v for k,v in term.items() if k!='body_text'},'cardHtml':markup(node,'index.html')})
        # Follow CSS font/image dependencies without publishing legacy scripts/data.
        done=set()
        while resources-done:
            rel=next(iter(resources-done)); done.add(rel)
            path=resource_path(built,rel)
            dest=public/rel; dest.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(path,dest)
            if path.suffix=='.css':
                for match in re.findall(r'url\(\s*[\"\']?([^\)\"\']+)',path.read_text(encoding='utf-8')):
                    if match.startswith('data:') or '://' in match: continue
                    resolved=site_relative(match,rel)
                    if resolved: resources.add(resolved[0])
        search_file=public/'assets/data/search-index.json';search_file.parent.mkdir(parents=True,exist_ok=True)
        search_file.write_text(json.dumps(data['search'],ensure_ascii=False,separators=(',',':')),encoding='utf-8')
        manifest={'schemaVersion':1,'sourceHash':report.input_hash,'topics':data['topics'],'terms':terms,'search':data['search'],
                  'pages':pages,'legacyOrigin':LEGACY,'routeMap':MIGRATED,
                  'assetCount':len(done)+1,'assetBytes':sum((public/rel).stat().st_size for rel in done)+search_file.stat().st_size}
        (generated/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
        views = public/'assets/data/views'
        views.mkdir(parents=True, exist_ok=True)
        for key in ('index','paths','variable','sem'):
            payload = {'topics':data['topics'],'terms':terms} if key=='index' else {
                'html':(generated/(key+'.html')).read_text(encoding='utf-8'),'metadata':pages[key]}
            (views/(key+'.json')).write_text(json.dumps({'schemaVersion':1,'key':key,
                'sourceHash':report.input_hash,'payload':payload},ensure_ascii=False,separators=(',',':')),encoding='utf-8')
        return manifest


def export_versioned(output, built, scope):
    """Read an already accepted build; no statistics or full site rebuild."""
    if scope != 'representative':
        raise ValueError('Full export is gated until representative acceptance')
    output = Path(output).resolve()
    built = built.resolve()
    if output == built or output.is_relative_to(built) or built.is_relative_to(output):
        raise ValueError('Source and export directories must be isolated')
    generated, public = output/'generated', output/'public'
    generated.mkdir(parents=True, exist_ok=True)
    public.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT/'site/assets/search.js', generated/'search.cjs')
    data = json.loads((built/'assets/data/site-data.js').read_text(encoding='utf-8').split('=',1)[1].strip().rstrip(';'))
    mapping = {'index': ('index.html','/'), 'paths': ('paths.html','/paths/'),
               'term:variable': ('terms/variable.html','/terms/variable/'),
               'term:sem': ('terms/sem.html','/terms/sem/')}
    routes = {page: route for page, route in mapping.values()}
    resources = {'assets/site.css','assets/favicon.svg','assets/favicon.ico','assets/vendor/katex/katex.min.css'}
    def url(value, page):
        if value.startswith('#'): return value
        resolved = site_relative(value, page)
        if resolved is None: return value
        relative, suffix = resolved
        if relative.endswith('.html') or not relative:
            relative = relative or 'index.html'
            return (BASE+'/'+relative if relative in routes else LEGACY+relative)+suffix
        resources.add(relative)
        return BASE+'/'+relative+suffix
    def markup(node, page):
        if isinstance(node,str): return node
        if node.tag == 'script': return ''
        attrs=[]
        for key,value in node.attrs.items():
            if key.startswith('on'): continue
            if value is None: attrs.append(key); continue
            if key in ('href','src'): value=url(value,page)
            if key=='srcset':
                value=', '.join(' '.join([url(parts[0],page)]+parts[1:]) for part in value.split(',') if (parts:=part.strip().split()))
            attrs.append(key+'="'+escape(value,quote=True)+'"')
        start='<'+node.tag+(' '+' '.join(attrs) if attrs else '')+'>'
        return start+('' if node.tag in VOID else ''.join(markup(c,page) for c in node.children)+'</'+node.tag+'>')
    pages, payloads, trees = {}, {}, {}
    for key,(page,route) in mapping.items():
        tree=Tree(resource_path(built,page).read_text(encoding='utf-8'));trees[key]=tree
        main=tree.root.find(lambda n:n.tag=='main')[0]
        html=''.join(markup(c,page) for c in main.children)
        title=''.join(c for n in tree.root.find(lambda n:n.tag=='title') for c in n.children if isinstance(c,str))
        term=next((t for t in data['search'] if t['id']==key.removeprefix('term:')),None)
        metadata={'title':title,'topic':term['topic'] if term else 'foundations'}
        record={'kind':'term' if key.startswith('term:') else key,**metadata,
                'canonicalPath':BASE+route,'aliases':[{'path':BASE+'/'+page}],
                'sourcePath':page,'resources':[]}
        record['formulaFonts']=formula_fonts(main, resource_path(built,'assets/vendor/katex/katex.min.css').read_text(encoding='utf-8'))
        pictures=main.find(lambda n:n.tag=='picture')
        first_images=(pictures[0].find(lambda n:n.tag=='img') if pictures else []) or main.find(lambda n:n.tag=='img')
        initial_image=first_images[0].attrs.get('src','') if first_images else None
        record['firstScreenResources']=[{'kind':'image','url':url(initial_image,page)}] if initial_image and key.startswith('term:') else []
        if pictures and record['firstScreenResources']:
            sources=[]
            for source in pictures[0].find(lambda n:n.tag=='source'):
                candidates=source.attrs.get('srcset','').split(',')[0].split()
                if candidates: sources.append({'media':source.attrs.get('media',''),'url':url(candidates[0],page)})
            if sources: record['firstScreenResources'][0]['sources']=sources
        blocks=[{'id':'body','html':html,'role':'body'}]
        frame='<!--psych-blocks-->'
        sequence=None
        articles=main.find(lambda n:'term-content' in n.attrs.get('class','').split())
        if articles:
            article=articles[0]
            inner=''.join(markup(c,page) for c in article.children)
            blocks=[{'id':c.attrs.get('id','block-'+str(i)), 'role':'header' if c.tag=='header' else 'section', 'html':markup(c,page)}
                    for i,c in enumerate(article.children) if isinstance(c,Node)]
            # Preserve whitespace text nodes as blocks as well, in exact order.
            blocks=[{'id':c.attrs.get('id','block-'+str(i)) if isinstance(c,Node) else 'space-'+str(i),
                     'role':('header' if c.tag=='header' else 'section') if isinstance(c,Node) else 'space',
                     'html':markup(c,page)} for i,c in enumerate(article.children)]
            frame=html.replace(inner,'<!--psych-blocks-->',1)
            seq=main.find(lambda n:'term-sequence' in n.attrs.get('class','').split())
            if seq:
                sequence=markup(seq[0],page)
                frame=frame.replace(sequence,'<!--psych-sequence-->',1)
        payload={'kind':record['kind'],'metadata':metadata,'blocks':blocks,'frameHTML':frame,'sequence':sequence}
        pages[key]=record;payloads[key]=payload
    cards=trees['index'].root.find(lambda n:'data-term' in n.attrs)
    by_id={node.attrs['data-id']:node for node in cards}
    terms=[]
    for term in data['search']:
        if term['id'] not in by_id: continue
        node=by_id[term['id']];node.attrs.pop('hidden',None)
        terms.append({**{k:v for k,v in term.items() if k!='body_text'},'cardHtml':markup(node,'index.html')})
    payloads['index']={'kind':'index','metadata':payloads['index']['metadata'],'blocks':[], 'topics':data['topics'],'terms':terms}
    digest=hashlib.sha256()
    for key in mapping: digest.update(resource_path(built,mapping[key][0]).read_bytes())
    for directory in ('components','lib','app'):
        for path in sorted((ROOT/'site/next-preview'/directory).rglob('*')):
            if path.is_file() and path.suffix in ('.jsx','.mjs','.css'): digest.update(path.read_bytes())
    digest.update(Path(__file__).read_bytes())
    done=set()
    while resources-done:
        rel=next(iter(resources-done));done.add(rel)
        path=resource_path(built,rel);dest=public/rel;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,dest)
        if path.suffix=='.css':
            for match in re.findall(r'url\(\s*[\"\']?([^\)\"\']+)',path.read_text(encoding='utf-8')):
                if match.startswith('data:') or '://' in match: continue
                resolved=site_relative(match,rel)
                if resolved: resources.add(resolved[0])
    digest.update((built/'assets/data/site-data.js').read_bytes())
    digest.update(json.dumps(payloads,ensure_ascii=False,sort_keys=True).encode())
    for rel in sorted(done):
        digest.update(rel.encode());digest.update(resource_path(built,rel).read_bytes())
    build_hash=digest.hexdigest()[:24]
    asset_urls={rel:BASE+'/'+rel+'?v='+build_hash for rel in done}
    def version_asset(value):
        parsed=urlsplit(unescape(value));rel=parsed.path.removeprefix(BASE+'/')
        if not parsed.path.startswith(BASE+'/') or rel not in asset_urls: return value
        query=[(k,v) for k,v in parse_qsl(parsed.query) if k!='v']+[('v',build_hash)]
        return parsed.path+'?'+urlencode(query)+('#'+parsed.fragment if parsed.fragment else '')
    def version_html(html):
        def attr(match):
            name,value=match.groups()
            if name=='srcset': value=', '.join(' '.join([version_asset(parts[0])]+parts[1:]) for entry in unescape(value).split(',') if (parts:=entry.strip().split()))
            else: value=version_asset(value)
            return name+'="'+escape(unescape(value),quote=True)+'"'
        return re.sub(r'(href|src|srcset)="([^"]*)"',attr,html)
    for payload in payloads.values():
        for block in payload['blocks']: block['html']=version_html(block['html'])
        if 'frameHTML' in payload: payload['frameHTML']=version_html(payload['frameHTML'])
        if payload.get('sequence'): payload['sequence']=version_html(payload['sequence'])
    for term in terms: term['cardHtml']=version_html(term['cardHtml'])
    for record in pages.values():
        for resource in record['firstScreenResources']:
            resource['url']=version_asset(resource['url'])
            for source in resource.get('sources',[]): source['url']=version_asset(source['url'])
    # Fonts/images referenced from CSS share the same immutable build identity.
    for rel in sorted(done):
        if Path(rel).suffix=='.css':
            css=resource_path(built,rel).read_text(encoding='utf-8')
            def css_url(match):
                value=match.group(1);resolved=site_relative(value,rel)
                return 'url("'+asset_urls[resolved[0]]+(('#'+urlsplit(value).fragment) if urlsplit(value).fragment else '')+'")' if resolved and resolved[0] in asset_urls else match.group(0)
            (public/rel).write_text(re.sub(r'url\(\s*[\"\']?([^\)\"\']+)[\"\']?\s*\)',css_url,css),encoding='utf-8')
    search_file=public/'assets/data/search-index.json';search_file.parent.mkdir(parents=True,exist_ok=True)
    search_file.write_text(json.dumps(data['search'],ensure_ascii=False,separators=(',',':')),encoding='utf-8')
    for key,payload in payloads.items():
        envelope={'schemaVersion':2,'buildHash':build_hash,'key':key,'payload':payload}
        text=json.dumps(envelope,ensure_ascii=False,separators=(',',':'))
        content_hash=hashlib.sha256(text.encode()).hexdigest()[:16]
        filename=key.replace(':','-')+'.'+content_hash+'.json'
        rel='assets/data/views/'+filename
        dest=public/rel;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_text(text,encoding='utf-8')
        pages[key].update(payloadURL=BASE+'/'+rel,payloadHash=content_hash,resources=sorted(asset_urls.values()))
        (generated/(key.replace(':','-')+'.json')).write_text(text,encoding='utf-8')
    manifest={'schemaVersion':2,'scope':scope,'buildHash':build_hash,'sourceHash':build_hash,'topics':data['topics'],'terms':terms,
              'pages':pages,'routeMap':routes,'legacyOrigin':LEGACY,'assetURLs':asset_urls,'searchURL':BASE+'/assets/data/search-index.json?v='+build_hash,'assetCount':len(done)+1,
              'assetBytes':sum((public/rel).stat().st_size for rel in done)+search_file.stat().st_size}
    (generated/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
    return manifest


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',default='site/next-preview');parser.add_argument('--source');parser.add_argument('--scope',default='representative');args=parser.parse_args()
    result=export_preview(Path(args.output),source_root=args.source,scope=args.scope)
    print(json.dumps({k:result[k] for k in ('schemaVersion','sourceHash','assetCount','assetBytes')},ensure_ascii=False))
