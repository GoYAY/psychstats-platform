"""Read-only graph projection of published knowledge-sidebars, not registry guesses."""
from collections import Counter
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
from urllib.parse import urlsplit
from term_explainer.library_export import public_catalogue

RELATIONS={'prerequisites','components','contrasts','used_in','next'}
FRAMEWORKS={
    'foundations':'心理统计基础框架',
    'hypothesis-testing':'效应量与假设检验框架',
    'group-comparisons':'差异检验与方差分析框架',
    'regression':'回归框架',
    'data-preparation':'数据准备框架',
    'classification-clustering':'分类与聚类框架',
    'factor-analysis':'因素分析框架',
    'structural-equation-modeling':'结构方程框架',
    'mediation-moderation':'中介与调节框架',
    'multilevel-longitudinal':'多层与纵向模型框架',
}
class Definition(HTMLParser):
    def __init__(self):super().__init__();self.sections=[];self.result=[];self.skip=0
    def handle_starttag(self,tag,attrs):
        if tag in ('script','style'):self.skip+=1
        if tag=='section':self.sections.append({'heading':[],'body':[],'h2':False,'wanted':False,'paragraph':False})
        if self.sections:
            if tag=='h2':self.sections[-1]['h2']=True
            if tag=='p':self.sections[-1]['paragraph']=True
    def handle_endtag(self,tag):
        if tag in ('script','style'):self.skip=max(0,self.skip-1)
        if not self.sections:return
        s=self.sections[-1]
        if tag=='h2':s['h2']=False;s['wanted']=''.join(s['heading']).strip()=='操作性定义'
        if tag=='p':s['paragraph']=False;s['body'].append('\n')
        if tag=='section':
            if s['wanted']:self.result.append(''.join(s['body']).strip())
            self.sections.pop()
    def handle_data(self,data):
        if self.skip or not self.sections:return
        s=self.sections[-1]
        if s['h2']:s['heading'].append(data)
        elif s['wanted'] and s['paragraph']:s['body'].append(data)

def published_definition(html):
    parser=Definition();parser.feed(html)
    return '\n'.join(p.strip() for p in parser.result if p.strip())

class Sidebar(HTMLParser):
    def __init__(self):super().__init__();self.stack=[];self.links=[]
    def handle_starttag(self,tag,attrs):
        a=dict(attrs);inside=any(s[1] for s in self.stack) or tag=='aside' and 'knowledge-sidebar' in a.get('class','').split()
        relation=a.get('data-relation') or next((s[2] for s in reversed(self.stack) if s[2]),None)
        if inside and tag=='a' and relation in RELATIONS:self.links.append((relation,a.get('href','')))
        if tag not in {'img','input','br','hr','meta','link','source','wbr','area','base','embed','param','track'}:self.stack.append((tag,inside,relation))
    def handle_endtag(self,tag):
        for i in range(len(self.stack)-1,-1,-1):
            if self.stack[i][0]==tag:self.stack=self.stack[:i];break

def official_graph(baseline,registry_path):
    baseline=Path(baseline);catalogue=public_catalogue(baseline)
    registry=json.loads(Path(registry_path).read_text(encoding='utf-8'))
    topics={t['id']:t.get('topic') for t in registry['terms']}
    terms=[dict(t,topic=topics.get(t['id'])) for t in catalogue['terms']]
    unknown=[t['id'] for t in terms if t['topic'] not in FRAMEWORKS]
    if unknown:raise ValueError('Published terms without an official topic: '+', '.join(unknown))
    known={t['id'] for t in terms};edges={};hashes={};warnings=[]
    for term in sorted(terms,key=lambda t:t['id']):
        filename='terms/'+term['id']+'.html';data=(baseline/filename).read_bytes();hashes[filename]=hashlib.sha256(data).hexdigest();p=Sidebar();p.feed(data.decode('utf-8'))
        term['definition']=published_definition(data.decode('utf-8'))
        for relation,href in p.links:
            path=urlsplit(href)
            if path.scheme or path.netloc:continue
            target=Path(path.path).stem
            if target not in known:
                warnings.append({'code':'MISSING_PUBLISHED_TARGET','page':filename,'target':target});continue
            if target==term['id']:continue
            ends=[term['id'],target]
            if relation=='contrasts':ends.sort()
            key=relation+'|official:'+ends[0]+'|official:'+ends[1]
            record={'page':filename,'from':term['id'],'to':target,'hash':hashes[filename]}
            if key not in edges:edges[key]={'key':key,'from':{'space':'official','id':ends[0]},'to':{'space':'official','id':ends[1]},'type':relation,'reason':'已发布术语页知识关系','origin':'official','status':'confirmed','sourceRecords':[]}
            if record not in edges[key]['sourceRecords']:edges[key]['sourceRecords'].append(record)
    frameworks=[]
    for identifier,title in FRAMEWORKS.items():
        core=sorted(t['id'] for t in terms if t['topic']==identifier);selected=set(core)
        related=[e for e in edges.values() if any(s['from'] in selected for s in e['sourceRecords'])]
        one_hop=sorted({r['id'] for e in related for r in [e['from'],e['to']]}-selected)
        counts=dict(Counter(e['type'] for e in related))
        frameworks.append(dict(id=identifier,title=title,core=core,oneHop=one_hop,edgeKeys=[e['key'] for e in related],edgeCounts=counts))
        if not counts.get('components'):warnings.append(dict(code='SPARSE_STRUCTURE',framework=identifier,message='已发布关系没有组成边；保留原有学习关系，不推断模型结构。'))
    return dict(schemaVersion=1,catalogueVersion=catalogue['catalogueVersion'],terms=terms,edges=sorted(edges.values(),key=lambda e:e['key']),frameworks=frameworks,sourceHashes=hashes,warnings=warnings)
