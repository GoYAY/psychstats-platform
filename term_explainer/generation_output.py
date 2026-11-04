"""Lossless model-shape normalization; strict lesson validation stays authoritative."""
from copy import deepcopy
from dataclasses import asdict,is_dataclass
import json
from .contract import validate_result
from .evidence import resolve_reference

TEACHING_BLOCKS=frozenset({'operational_definition','plain_explanation','detailed_explanation','how_to_use'})


class LessonOutputError(ValueError):
    def __init__(self,issues):
        self.issues=issues[:20]
        super().__init__(json.dumps(dict(validation_issues=self.issues,additional_issues=max(0,len(issues)-20)),ensure_ascii=False))


def teaching_body_source_ids(value):
    value=asdict(value) if is_dataclass(value) else value
    result=set()
    if not isinstance(value,dict) or not isinstance(value.get('blocks'),list):return result
    for block in value['blocks']:
        if not isinstance(block,dict) or not isinstance(block.get('id'),str) or block['id'].replace('-','_') not in TEACHING_BLOCKS:continue
        if not isinstance(block.get('paragraphs'),list):continue
        for p in block['paragraphs']:
            if not isinstance(p,dict) or p.get('kind')!='factual' or not isinstance(p.get('refs'),list):continue
            result.update(r['source_id'] for r in p['refs'] if isinstance(r,dict) and isinstance(r.get('source_id'),str))
    return result


def validate_generated_lesson(value,request,*,additional_issues=(),visual_policy_version=0):
    data=deepcopy(value);changes=[];issues=deepcopy(list(additional_issues))
    def issue(path,message):
        item=dict(path=path,message=str(message))
        if item not in issues:issues.append(item)
    def change(path,operation):changes.append(dict(path=path,operation=operation))
    if isinstance(data,dict):
        visual=data.get('visual')
        if isinstance(visual,dict):
            from .visual_presentation import validate_presentation
            try:validate_presentation(visual,required=visual_policy_version==1)
            except (ValueError,TypeError) as error:issue('/visual/presentation',error)
            payload=visual.get('payload',{})
            if visual.get('kind')=='statistical' and isinstance(payload,dict):
                if visual_policy_version==1 and payload.get('y_unit') in {'%','％'} and not isinstance(visual.get('data_semantics'),dict):
                    issue('/visual/data_semantics','declare partition (mutually exclusive and exhaustive) or independent percentage observations, denominator or null, and rounding_digits; do not infer that all percent series sum to 100')
                series=payload.get('series',[])
                for i,s in enumerate(series if isinstance(series,list) else []):
                    if not isinstance(s,dict):continue
                    for key in (('bin_edges','counts') if payload.get('chart_type')=='histogram' else ('x','y')):
                        if not isinstance(s.get(key),list):issue(f'/visual/payload/series/{i}/{key}','must be an array; preserve observations and categories, do not invent values')
        term=data.get('term')
        if (isinstance(term,dict) and request.term.get('definition','')==''
                and isinstance(term.get('definition'),str) and term['definition']
                and all(term.get(k,'')==request.term.get(k,'') for k in ('id','zh','en'))):
            term['definition']=''
            change('/term/definition','discard_unrequested_definition_metadata_preserve_user_anchor')
        blocks=data.get('blocks',[])
        for bi,block in enumerate(blocks if isinstance(blocks,list) else []):
            if not isinstance(block,dict):continue
            paragraphs=block.get('paragraphs',[])
            for pi,p in enumerate(paragraphs if isinstance(paragraphs,list) else []):
                if not isinstance(p,dict):continue
                path=f'/blocks/{bi}/paragraphs/{pi}/emphasis'
                if isinstance(p.get('emphasis'),str):
                    p['emphasis']=[p['emphasis']]
                    change(path,'single_string_to_one_item_list')
                if isinstance(p.get('text'),str) and isinstance(p.get('emphasis'),list):
                    original=p['text']
                    for phrase in p['emphasis']:
                        if isinstance(phrase,str) and phrase:p['text']=p['text'].replace('**'+phrase+'**',phrase)
                    if p['text']!=original:change(f'/blocks/{bi}/paragraphs/{pi}/text','selected_markdown_emphasis_to_semantic_field')
                if 'emphasis' in p and not isinstance(p['emphasis'],list):issue(path,'emphasis must be an array of phrases present in text')
                if p.get('kind')=='factual' and not p.get('refs'):issue(f'/blocks/{bi}/paragraphs/{pi}/refs','factual explanation requires locatable source evidence')
        edges=data.get('source_relations',[])
        for ei,edge in enumerate(edges if isinstance(edges,list) else []):
            if not isinstance(edge,dict):continue
            path=f'/source_relations/{ei}'
            try:
                def positions(items):
                    if not isinstance(items,list):raise ValueError('source relation evidence must be an array')
                    return [resolve_reference(r,request.sources,allow_locator=edge.get('type')=='cites') for r in items]
                if 'refs' in edge:
                    alias=positions(edge['refs'])
                    if 'evidence' in edge and positions(edge['evidence'])!=alias:raise ValueError('conflicting refs and evidence; source meaning must not be guessed')
                    edge.pop('refs');edge['evidence']=alias
                    change(path,'refs_alias_to_evidence')
                elif 'evidence' in edge:
                    resolved=positions(edge['evidence'])
                    if resolved!=edge['evidence']:change(path+'/evidence','span_ids_to_source_coordinates')
                    edge['evidence']=resolved
            except (ValueError,KeyError,TypeError) as error:issue(path+'/evidence',error)
        limits=data.get('limitations',[])
        for ni,note in enumerate(limits if isinstance(limits,list) else []):
            if isinstance(note,dict) and not note.get('refs'):issue(f'/limitations/{ni}/refs','research limits require source evidence')

    # Independent reference failures are returned together, rather than one paid
    # repair per invalid paragraph. This preflight never substitutes for validation.
    def scan(node,path=''):
        if isinstance(node,list):
            for i,item in enumerate(node):scan(item,f'{path}/{i}')
        elif isinstance(node,dict):
            for key,item in node.items():
                if key=='refs':
                    if not isinstance(item,list):issue(path+'/refs','refs must be an array');continue
                    for i,ref in enumerate(item):
                        try:resolve_reference(ref,request.sources)
                        except (ValueError,KeyError,TypeError) as error:issue(f'{path}/refs/{i}',error)
                elif key!='provenance':scan(item,path+'/'+key)
    scan(data)
    try:lesson=validate_result(data,request)
    except (ValueError,KeyError,TypeError) as error:
        if not any(i['message']==str(error) for i in issues):issue('/',error)
        lesson=None
    if issues:raise LessonOutputError(issues)
    return lesson,changes
