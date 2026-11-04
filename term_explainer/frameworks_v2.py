"""Typed organization proposals; inferred relationships never claim source evidence."""
from copy import deepcopy
import json
from pathlib import Path
from .frameworks import bad, fields, string, identifier, array, refkey, input_hash

RELATIONS=('prerequisites','components','contrasts','used_in','next')

def key(ref,allow_new=False):
    if allow_new and isinstance(ref,dict) and ref.get('space')=='new':
        fields(ref,['space','id']);identifier(ref['id']);return 'new:'+ref['id']
    return refkey(ref)

def validate_input(value):
    from .frameworks import validate_input as validate_v1
    fields(value,['schemaVersion','terms','frameworks','relations'])
    if type(value['schemaVersion']) is not int or value['schemaVersion']!=2:bad('不支持的语义整理版本。')
    legacy=deepcopy(value);legacy['schemaVersion']=1
    for f in array(legacy['frameworks'],60):
        fields(f,['id','title','description','members','revision','locks','scope','memberDetails','excludedMembers'])
        string(f.pop('scope'),1500,True);members={key(r) for r in f['members']};seen=set()
        for row in array(f.pop('memberDetails'),200):
            fields(row,['ref','role','reason']);k=key(row['ref']);string(row['reason'],1500)
            if k not in members or k in seen or row['role'] not in ('core','supporting','existing'):bad('成员角色身份无效。')
            seen.add(k)
        if seen!=members:bad('成员角色不完整。')
        seen=set()
        for row in array(f.pop('excludedMembers'),5000):
            fields(row,['ref','reason']);k=key(row['ref']);string(row['reason'],1500)
            if k in members or k in seen:bad('框架排除决定冲突。')
            seen.add(k)
    for r in array(legacy['relations'],5000):
        fields(r,['from','to','type','basis'])
        if r.pop('basis') not in ('literature','inference','manual','official'):bad('关系依据无效。')
    validate_v1(legacy)
    try:size=len(json.dumps(value,ensure_ascii=False,allow_nan=False).encode('utf-8'))
    except (ValueError,TypeError):bad('整理摘要不能编码。')
    if size>512*1024:bad('整理摘要超过512KiB。')
    return deepcopy(value)

def _cycles(edges):
    adjacency={}
    for r in edges:
        if r['type']=='prerequisites':adjacency.setdefault(key(r['from'],True),set()).add(key(r['to'],True))
    active=set();done=set()
    def visit(k):
        if k in active:bad('前置知识关系形成循环。')
        if k in done:return
        active.add(k)
        for nxt in adjacency.get(k,()):visit(nxt)
        active.remove(k);done.add(k)
    for k in adjacency:visit(k)

def validate_output(value,payload):
    payload=validate_input(payload);fields(value,['schemaVersion','groups','contexts','relations','reviews','unassigned'])
    if type(value['schemaVersion']) is not int or value['schemaVersion']!=2:bad('模型响应版本无效。')
    terms={key(t['ref']):t for t in payload['terms']};frames={f['id']:f for f in payload['frameworks']};new={}
    for c in array(value['contexts'],20):
        fields(c,['localId','name','aliases','definition','reason']);identifier(c['localId'])
        k='new:'+c['localId']
        if k in new:bad('新简释身份重复。')
        for field,maxlen in [('name',120),('definition',1500),('reason',1500)]:string(c[field],maxlen)
        for alias in array(c['aliases'],30):string(alias,120)
        new[k]=c
    known=set(terms)|set(new);covered=set();new_members=set();targets=set()
    for group in array(value['groups'],30):
        fields(group,['targetFrameworkId','title','description','scope','members'])
        string(group['title'],120);string(group['description'],1500,True);string(group['scope'],1500)
        target=group['targetFrameworkId']
        if target is not None:
            if not isinstance(target,str) or target not in frames or target in targets:bad('框架目标缺失或重复。')
            targets.add(target)
        seen=set()
        for row in array(group['members'],220):
            fields(row,['ref','role','reason']);k=key(row['ref'],True);string(row['reason'],1500)
            if k not in known or k in seen or row['role'] not in ('core','supporting'):bad('模型成员身份或角色无效。')
            if k in terms and not (terms[k]['definition'].strip() or terms[k]['summary'].strip()):bad('仅名称的概念应未归类。')
            seen.add(k)
            if k in terms:covered.add(k)
            else:new_members.add(k)
        if not seen.intersection(terms):bad('框架须锚定已有概念，不能全由新词组成。')
    linked=set();relation_keys=set()
    for r in array(value['relations'],200):
        fields(r,['from','to','type','reason']);a=key(r['from'],True);b=key(r['to'],True);string(r['reason'],1500)
        if a not in known or b not in known or a==b or r['type'] not in RELATIONS:bad('关系目标或类型无效。')
        ends=sorted((a,b)) if r['type']=='contrasts' else (a,b);signature=(r['type'],*ends)
        if signature in relation_keys:bad('关系重复。')
        relation_keys.add(signature)
        if a in new and b in terms:linked.add(a)
        if b in new and a in terms:linked.add(b)
    if new_members!=set(new) or linked!=set(new):bad('每个新背景概念须入组并与已有概念有具体关系。')
    _cycles([*payload['relations'],*value['relations']])
    reviewed=set()
    for row in array(value['reviews'],200):
        fields(row,['frameworkId','ref','action','reason']);identifier(row['frameworkId']);k=key(row['ref']);string(row['reason'],1500)
        frame=frames.get(row['frameworkId'])
        if not frame or k not in {key(r) for r in frame['members']} or k not in terms or row['action'] not in ('keep','remove') or (row['frameworkId'],k) in reviewed:bad('成员审查目标无效。')
        reviewed.add((row['frameworkId'],k))
    unassigned=[key(r) for r in array(value['unassigned'],200)]
    if len(set(unassigned))!=len(unassigned) or any(k not in terms or k in covered for k in unassigned) or covered|set(unassigned)!=set(terms):bad('输入概念遗漏或分组状态冲突。')
    return deepcopy(value)

def analyze_frameworks(payload,client):
    payload=validate_input(payload)
    reference=Path(__file__).parent/'skills/explain-research-term/references/framework-organization.md'
    instruction=reference.read_text(encoding='utf-8')
    before=client.calls
    reply=client.generate([{'role':'system','content':instruction},{'role':'user','content':json.dumps(payload,ensure_ascii=False)}])
    try:raw=json.loads(reply.content)
    except (TypeError,ValueError):bad('模型未返回有效整理JSON。')
    result=validate_output(raw,payload)
    usage={k:reply.usage.get(k) for k in ('prompt_tokens','completion_tokens','total_tokens')}
    if any(type(n) is not int or n<0 for n in usage.values()) or client.calls-before!=1:bad('缺少可核对的单次调用用量。')
    return dict(result,inputHash=input_hash(payload),model=reply.model,usage=usage,calls=1)
