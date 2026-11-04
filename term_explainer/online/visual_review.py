"""One evidence-bounded review; no search, rendering code or public projection."""
from copy import deepcopy
from pathlib import Path
import json,re
from ..evidence import resolve_reference
from ..pipeline import _parse
from ..visual_presentation import validate_presentation
from ..visual_preservation import WORDING_FIELDS

def requires_visual_review(visual):
    p=validate_presentation(visual)
    return p is not None

def build_review_context(request,lesson,sources):
    visual=deepcopy(lesson['visual']);blocks=[];refs=list(visual.get('refs',[]))
    for b in lesson['blocks']:
        if b['id'] not in ('operational_definition','plain_explanation'):continue
        blocks.append(dict(id=b['id'],paragraphs=[dict(text=p['text']) for p in b['paragraphs']]))
        refs.extend(r for p in b['paragraphs'] for r in p.get('refs',[]))
    evidence=[];seen=set();indexed={s['id']:s for s in sources}
    for ref in refs:
        r=resolve_reference(ref,sources);key=(r['source_id'],r['start'],r['end'])
        if key in seen:continue
        seen.add(key);evidence.append(dict(r,text=indexed[r['source_id']]['text'][r['start']:r['end']]))
    limitations=[n['text'] for n in lesson.get('limitations') or []
                 if isinstance(n,dict) and isinstance(n.get('text'),str) and n['text'].strip()]
    context=dict(term=deepcopy(request['term']),blocks=blocks,visual=visual,evidence=evidence)
    # Only a page that actually discloses a limited evidence scope says so; the
    # field stays out of the wire request otherwise so saved receipts keep their hash.
    if limitations:context['limitations']=limitations
    if request.get('allow_limited_delivery'):
        # The page is authorized to answer from the material actually read; the
        # reviewer judges the figure against that material, not against sources
        # nobody supplied.
        context['delivery_policy']=dict(limited_evidence_accepted=True,
            note='本次以已读资料交付，资料广度已由产品接受；不要求补齐更多文献。')
    return context

def validate_review(value,context,sources):
    if not isinstance(value,dict) or set(value)!={'decision','reason','object_paths','refs'}:raise ValueError('Invalid visual review fields')
    if value['decision'] not in ('pass','revise','uncertain'):raise ValueError('Invalid review decision')
    reason=value['reason']
    if not isinstance(reason,str) or not 0<len(reason.strip())<=500 or re.search(r'https?://|javascript:|```|<script',reason,re.I):raise ValueError('Invalid review reason')
    paths=value['object_paths']
    if not isinstance(paths,list) or len(paths)>12 or len(set(p for p in paths if isinstance(p,str)))!=len(paths) or (not paths and value['decision']!='uncertain'):raise ValueError('Review requires actual object paths')
    for path in paths:
        wording=(isinstance(path,str) and path in {'/'+key for key in WORDING_FIELDS}
                 and context.get('wording_authorization_version')==1)
        if not isinstance(path,str) or (not path.startswith('/payload/') and not wording):raise ValueError('Invalid object pointer')
        if 'review_targets' in context and path not in {t['path'] for t in context['review_targets']}:raise ValueError('Pointer outside host review catalogue')
        node=context['visual']
        try:
            for part in path[1:].split('/'):
                part=part.replace('~1','/').replace('~0','~')
                if isinstance(node,list):
                    if not re.fullmatch(r'0|[1-9][0-9]*',part):raise ValueError('Invalid index')
                    node=node[int(part)]
                else:node=node[part]
        except (KeyError,IndexError,TypeError):raise ValueError('Unknown visual object') from None
        if wording:
            if not isinstance(node,str) or not node.strip():raise ValueError('Pointer must identify existing wording')
        elif not isinstance(node,(dict,list)):raise ValueError('Pointer must identify an object or collection')
    if not isinstance(value['refs'],list):raise ValueError('Review refs must be an array')
    allowed={(r['source_id'],r['start'],r['end']) for r in context['evidence']}
    for ref in value['refs']:
        r=resolve_reference(ref,sources)
        if (r['source_id'],r['start'],r['end']) not in allowed:raise ValueError('Review reference outside selected evidence')
    return deepcopy(value)

def review_targets(visual,*,allow_wording=False):
    """Host-owned containers plus v4's three explicit wording fields."""
    targets=[]
    def walk(node,path):
        if not isinstance(node,(dict,list)):return
        if path!='/payload':targets.append(dict(path=path,kind='object' if isinstance(node,dict) else 'collection'))
        children=node.items() if isinstance(node,dict) else enumerate(node)
        for key,value in children:
            escaped=str(key).replace('~','~0').replace('/','~1')
            walk(value,path+'/'+escaped)
    walk(visual['payload'],'/payload')
    if allow_wording:
        targets.extend(dict(path='/'+key,kind='wording') for key in WORDING_FIELDS
                       if isinstance(visual.get(key),str) and visual[key].strip())
    return targets

def review_visual(request,lesson,sources,provider,*,policy_version=3):
    if type(policy_version) is not int or policy_version not in (1,2,3,4):raise ValueError('Unknown visual review policy')
    context=build_review_context(request,lesson,sources)
    if policy_version in (2,3,4):
        context.update(question=request.get('question',''),review_targets=review_targets(lesson['visual'],allow_wording=policy_version==4))
    if policy_version==4:context['wording_authorization_version']=1
    name={1:'visual-review-v1.md',2:'visual-review.md',3:'visual-review-v3.md',4:'visual-review-v4.md'}[policy_version]
    prompt=(Path(__file__).parents[1]/'skills/explain-research-term/references'/name).read_text(encoding='utf-8')
    reply=provider.generate([dict(role='system',content=prompt),dict(role='user',content=json.dumps(context,ensure_ascii=False))])
    return validate_review(_parse(reply),context,sources)
