"""Source-backed inline notes and verified catalogue routes; no network or HTML eval."""
from html import escape
import json
from pathlib import Path
import re


def _names(item):
    return [n for n in [item.get('term'),item.get('zh'),item.get('en'),*item.get('aliases',[])] if isinstance(n,str) and n.strip()]


def classic_catalogue():
    """Use actual built term pages, not early fixtures or arbitrary model URLs."""
    site=Path(__file__).resolve().parents[1]/'site/dist'
    path=site/'assets/data/search-index.json'
    if not path.is_file(): return []
    values=json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(values,list): return []
    return [dict(id=t['id'],zh=t['zh'],en=t.get('en',''),aliases=t.get('aliases',[]),
                 summary=t.get('summary',''),kind='classic') for t in values
            if re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,95}',t.get('id',''))
            and (site/'terms'/(t['id']+'.html')).is_file()]


def _emphasize(text,phrases):
    choices=sorted({p for p in phrases if p},key=len,reverse=True)
    if not choices: return escape(text)
    pattern=re.compile('|'.join(re.escape(p) for p in choices))
    out=[]; end=0
    for m in pattern.finditer(text):
        out.extend([escape(text[end:m.start()]),'<strong>'+escape(m.group())+'</strong>']);end=m.end()
    return ''.join(out)+escape(text[end:])


class InlineGlossary:
    def __init__(self,entries,catalog,current):
        self.current=current; self.used=set(); self.notes={}; self.candidates={}
        # Catalogue metadata (including stored/model-provided kind) is not proof
        # that a page exists. Keep all names for matching, allow only built routes.
        self.published_ids={t['id'] for t in classic_catalogue()}
        self.catalog={t['id']:t for t in catalog if re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,95}',t.get('id',''))}
        def add(name,kind,value):
            if len(name)==1 and name.isascii(): return
            entry=self.candidates.setdefault(name.casefold(),dict(label=name,glossary=[],catalog=[],self=False))
            if kind=='self': entry[kind]=value
            else: entry[kind].append(value)
        for term in self.catalog.values():
            for name in _names(term): add(name,'catalog',term['id'])
        for entry in entries:
            self.notes[entry['id']]=dict(title=entry['term'],explanation=entry['explanation'],href=self.target(entry))
            for name in _names(entry): add(name,'glossary',entry['id'])
        for name in _names(current): add(name,'self',True)
        parts=[]
        for value in sorted(self.candidates.values(),key=lambda c:len(c['label']),reverse=True):
            name=value['label']; part=re.escape(name)
            if re.match(r'[A-Za-z0-9_]',name[0]): part=r'(?<![A-Za-z0-9_])'+part
            if re.match(r'[A-Za-z0-9_]',name[-1]): part+=r'(?![A-Za-z0-9_])'
            parts.append(part)
        # Case-insensitive ASCII method names must not absorb dotted-I/long-S
        # lookalikes that have different dictionary keys or technical meanings.
        self.pattern=re.compile('|'.join(parts),re.I|re.ASCII) if parts else None

    def url(self,key):
        term=self.catalog.get(key,{})
        if key not in self.published_ids or key==self.current['id'] or term.get('kind')!='classic' or term.get('status','public')!='public': return None
        return 'https://cdst.site/psy-stats/terms/'+key+'.html'

    def target(self,entry):
        if entry.get('target'): return self.url(entry['target'])
        names={n.casefold() for n in _names(entry)}
        matches={t['id'] for t in self.catalog.values() if names.intersection(n.casefold() for n in _names(t))}
        return self.url(next(iter(matches))) if len(matches)==1 else None

    def render(self,text,emphasis=()):
        if not self.pattern: return _emphasize(text,emphasis)
        out=[]; end=0
        for match in self.pattern.finditer(text):
            out.append(_emphasize(text[end:match.start()],emphasis)); label=match.group()
            entry=self.candidates[label.casefold()]; key=None; href=None
            if not entry['self']:
                choices=set(entry['glossary'])
                if len(choices)==1:
                    key=next(iter(choices)); href=self.notes[key]['href']
            content=_emphasize(label,[p for p in emphasis if p in label or label in p])
            if not key: out.append(content)
            else:
                self.used.add(key)
                attrs=' type="button" data-note="'+escape(key,quote=True)+'" aria-controls="term-popover" aria-expanded="false" aria-haspopup="dialog" aria-describedby="term-popover-hint"'
                out.append('<button class="term-help"'+attrs+'>'+content+'</button>')
            end=match.end()
        return ''.join(out)+_emphasize(text[end:],emphasis)

    def markup(self):
        if not self.used: return ''
        public={key:self.notes[key] for key in sorted(self.used)}
        encoded=json.dumps(public,ensure_ascii=False).replace('<','\\u003c')
        return ('<span id="term-popover-hint" class="term-sr-only">按 Enter 或空格打开解释；打开后按向下箭头进入浮窗，按 Esc 关闭。</span>'
                '<div id="term-popover" class="term-popover" role="dialog" tabindex="-1" aria-modal="false" aria-labelledby="term-popover-title" aria-describedby="term-popover-description" hidden>'
                '<div id="term-popover-title" class="term-popover-title"></div><p id="term-popover-description"></p>'
                '<a id="term-popover-link" hidden>查看完整科普 →</a></div>'
                '<script type="application/json" id="term-notes">'+encoded+'</script>')
