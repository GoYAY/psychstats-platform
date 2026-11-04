"""Verified section routing around the existing source-first teaching pipeline."""
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path
import hashlib,re
from collections import Counter
from .config import OnlineError
from .store import identifier
from ..contract import validate_request
from ..pipeline import prepare_evidence,_normalize_fetched_scope
from ..section_reading import create_reading_state,read_next_section
from ..full_job import select_evidence,JobError
from ..section_quality import validate_identity_review
from ..section_structure import explicit_heading,heading_role,body_sections,NUMBERED

def normalize_pdf_text(text):
    count=text.count('\x00')
    return text.replace('\x00','\ufffd'),([f'PDF有{count}处无法映射的字形，已保留为替代符；相关公式须核对原件。'] if count else [])

def exact_identity_review(source,*,header_end=None):
    """Located literal title matching, never a scientific/publisher endorsement."""
    title=''.join(c for c in source.get('title','') if not c.isspace()).casefold()
    if len(title)<12:return None
    chars=[];indices=[]
    for i,c in enumerate(source['text'][:12000]):
        if not c.isspace():
            folded=c.casefold();chars.extend(folded);indices.extend([i]*len(folded))
    at=''.join(chars).find(title)
    if at<0:return None
    review=dict(status='matches',source_id=source['id'],source_hash=hashlib.sha256(source['text'].encode()).hexdigest(),bibliography={k:source.get(k,[] if k=='authors' else None if k=='year' else '') for k in ('title','authors','year','doi')},reviewer='local_exact_title_match',evidence=[dict(source_id=source['id'],start=indices[at],end=indices[at+len(title)-1]+1)])
    if source.get('doi'):
        # A DOI somewhere in a paper may identify a cited work. Without a
        # located article-header boundary it cannot certify this article.
        if header_end is None:return None
        found=re.search(r'(?<![a-z0-9])'+re.escape(source['doi'])+r'(?![a-z0-9/])',source['text'][:header_end],re.I)
        if not found:return None
        review['evidence'].append(dict(source_id=source['id'],start=found.start(),end=found.end()))
    return validate_identity_review(review,source)

HEADINGS=re.compile(r'^(?:#{1,6}\s+.{1,160}|[0-9]{1,2}(?:\.[0-9]{1,2})*[.)]?\s+[A-Z\u4e00-\u9fff][^.!?。！？\n]{1,100}|Abstract|Introduction|Methods?|Results?|Discussion|Conclusions?|References|Appendix(?:\s+\w+)?|摘要|引言|方法|结果|讨论|结论|参考文献|附录)\s*$')

def _source_set_context(documents):
    sources=[d['source'] for d in documents];mentions=[]
    for source in sources:
        chars=[];offsets=[]
        for i,c in enumerate(source['text']):
            if re.match(r'\w',c):
                folded=c.casefold();chars.extend(folded);offsets.extend([i]*len(folded))
        haystack=''.join(chars)
        for other in sources:
            if source['id']==other['id']:continue
            title=re.sub(r'\W+','',other['title']).casefold()
            if len(title)<12:continue
            at=haystack.find(title)
            if at>=0:mentions.append(dict(source_id=source['id'],mentioned_source_id=other['id'],start=offsets[at],end=offsets[at+len(title)-1]+1))
    return dict(role='reading_plan_and_title_locators_not_scientific_evidence',sources=[{k:s.get(k,'') for k in ('id','title','doi')} for s in sources],title_mentions=mentions)

def _headings(text):
    rows=[];offset=0
    for line in text.splitlines(keepends=True):
        title=line.strip()
        found=explicit_heading(title) if title else None
        if title and (found or HEADINGS.fullmatch(title)):rows.append(dict(title=found or title,start=offset+len(line)-len(line.lstrip())))
        offset+=len(line)
    if not rows:
        if len(text)>6000:raise OnlineError('source_needs_structure','没有可靠的小节边界，请提供带章节标题的文字版材料。')
        first=text.splitlines()[0]
        rows=[dict(title=first,start=0)]
    return rows

def _pdf_structure(layouts,parts,toc):
    """Locate real layout/TOC headings in unchanged extracted page text."""
    pages=[];styles=Counter();offset=0
    for page,text in zip(layouts,parts):
        blocks=[]
        for block in page['blocks']:
            lines=[]
            for line in block.get('lines',[]):
                spans=line['spans'];label=''.join(s['text'] for s in spans).strip().replace('\x00','\ufffd')
                if not label:continue
                found=re.search(r'(?m)^[ \t]*'+re.escape(label)+r'[ \t]*(?:\n|$)',text)
                if found:
                    begin=found.start()+len(found[0])-len(found[0].lstrip(' \t'))
                    lines.append(dict(title=label,start=offset+begin,size=max(s['size'] for s in spans),bold=all(s['flags']&16 for s in spans),chars=sum(len(s['text']) for s in spans)))
                for s in spans:styles[round(s['size'],1)]+=len(s['text'])
            if lines:blocks.append(lines)
        pages.append(blocks);offset+=len(text)+1
    if not styles:return [],''
    body=styles.most_common(1)[0][0];rows={}
    def put(row):
        title=row['title']
        if (3<=len(title)<=180 or explicit_heading(title)==title) and any(c.isalpha() for c in title) and not re.search(r'[=<>]|https?://|^arXiv:|^(?:Figure|Table)\s+\d',title,re.I):rows[row['start']]=dict(title=title,start=row['start'])
    normalize=lambda value:re.sub(r'\W+','',value).casefold()
    for level,title,page_number,*_ in toc:
        if not 1<=page_number<=len(pages):continue
        target=normalize(title)
        for block in pages[page_number-1]:
            if normalize(' '.join(r['title'] for r in block))==target or any(normalize(r['title'])==target for r in block):
                row=next((r for r in block if target.startswith(normalize(r['title']))),block[0]);put(row)
    for blocks in pages:
        for block in blocks:
            for row in block:
                prefix=explicit_heading(row['title'])
                if prefix and (not NUMBERED.match(prefix) or row['size']>=body-.15):put(dict(row,title=prefix))
            # Whole short blocks: avoid inline bold run-in labels and equations.
            if sum(len(r['title']) for r in block)>180:continue
            first=block[0]
            standard=bool(re.fullmatch(r'Abstract|Introduction|Methods?|Results?|Discussion|Conclusions?|References|Appendix(?:\s+\w+)?|摘要|引言|方法|结果|讨论|结论|参考文献|附录',first['title'],re.I))
            if standard or all(r['size']>=body+0.8 or (r['bold'] and r['size']>=body-.1) for r in block):put(first)
    title='';title_start=None
    if pages:
        abstracts=[r['start'] for r in rows.values() if heading_role(r['title'])=='abstract']
        first_abstract=min(abstracts) if abstracts else None
        candidates=[block for block in pages[0] if 3<=sum(len(r['title']) for r in block)<=500 and all(r['size']>=body+1.5 for r in block) and not explicit_heading(block[0]['title']) and (first_abstract is None or block[0]['start']<first_abstract) and not any(re.search(r'@|https?://|^arXiv:',r['title'],re.I) for r in block)]
        if candidates:
            chosen=max(candidates,key=lambda b:(min(r['size'] for r in b),sum(r['chars'] for r in b)))
            title=' '.join(r['title'] for r in chosen).replace('- ','-')
            if not explicit_heading(chosen[0]['title']):title_start=chosen[0]['start']
    ordered=[rows[k] for k in sorted(rows)]
    # The identified article-title block preceding a real abstract is metadata.
    # Preserve its text and boundary; do not count title+authors as body evidence.
    if title_start in rows and any(heading_role(r['title'])=='abstract' and r['start']>title_start for r in ordered):
        rows[title_start]['role']='front_matter'
    whole='\n'.join(parts);merged=[]
    for row in ordered:
        # Only a numbered parent immediately followed by its own child may
        # share a reading unit. A title adjacent to a body/abstract heading
        # must not consume that heading (and erase the header/body boundary).
        if merged and not whole[merged[-1]['start']+len(merged[-1]['title']):row['start']].strip():
            parent=NUMBERED.match(merged[-1]['title']);child=NUMBERED.match(row['title'])
            if parent and child:
                parent_number=re.match(r'\d+(?:\.\d+)*',parent[0])[0]
                child_number=re.match(r'\d+(?:\.\d+)*',child[0])[0]
                if child_number.startswith(parent_number+'.'):continue
        merged.append(row)
    return merged,title

def parse_source(file,descriptor,limits):
    path=Path(file)
    if path.stat().st_size>limits.max_file_bytes:raise OnlineError('file_too_large','文件超过允许大小。',413)
    raw=path.read_bytes();mime=descriptor.get('mime');metadata_title='';pdf_headings=None;warnings=[];extraction=None;header_doi='';header_end=None
    if mime=='application/pdf':
        if not raw.startswith(b'%PDF-'):raise OnlineError('invalid_source','文件内容不是PDF。')
        try:
            from ..pdf_runtime import extract_document
            pdf=extract_document(raw,max_pages=limits.max_pages,max_chars=min(limits.max_text_chars,120000))
            extraction=pdf['extraction'];metadata_title=' '.join(pdf['title'].split())[:500];parts=[]
            for value in pdf['parts']:
                value,notes=normalize_pdf_text(value);warnings.extend(notes);parts.append(value)
            text='\n'.join(parts)
            pdf_headings,layout_title=_pdf_structure(pdf['layouts'],parts,pdf['toc'])
            if not metadata_title or re.search(r'\d.*(?:\.\.|\.pdf$|_EPM)|^\d+_|Microsoft\s+Word|\.(?:docx?|pdf)$',metadata_title,re.I):metadata_title=layout_title or metadata_title
            # Only the article's header can supply a missing DOI. Never infer it
            # from a cited paper in the references or from the upload filename.
            normalize=lambda value:re.sub(r'\W+','',value).casefold()
            # Include typographic/custom body headings, excluding only located
            # title rows. Missing boundaries never authorize a whole-paper scan.
            boundaries=[h['start'] for h in pdf_headings if not (layout_title and normalize(layout_title).startswith(normalize(h['title'])))]
            header_end=min([len(parts[0]),6000,*boundaries]) if boundaries else 0
            header=text[:header_end]
            dois={m.group(0).rstrip('.,;。)').casefold() for m in re.finditer(r'10\.\d{4,9}/[^\s<>"\u3000]+',header,re.I)}
            if len(dois)==1:header_doi=next(iter(dois))
        except OnlineError:raise
        except Exception:raise OnlineError('source_unreadable','PDF未能安全读取，请提供文字版材料。') from None
    elif mime=='text/plain':
        try:text=raw.decode('utf-8-sig').replace('\r\n','\n').replace('\r','\n')
        except UnicodeError:raise OnlineError('source_unreadable','请提供UTF-8文字材料。') from None
    else:raise OnlineError('invalid_source','当前只支持PDF和UTF-8文本。')
    if not text.strip() or '\x00' in text:raise OnlineError('source_unreadable','材料没有可读取文字，请提供文字版；本轮不自动OCR。')
    if len(text)>min(limits.max_text_chars,120000):raise OnlineError('source_too_large','文字超过当前单篇阅读限制，未截断材料。',413)
    headings=pdf_headings if pdf_headings else _headings(text) if mime=='text/plain' or len(text)<=6000 else []
    if not headings:raise OnlineError('source_needs_structure','没有可核对的小节边界，请提供带章节标题的文字版材料。')
    if not body_sections(text,headings):raise OnlineError('source_needs_structure','未识别到可读取的正文小节；请补充带清晰正文标题的材料。')
    sha=hashlib.sha256(raw).hexdigest()
    source=dict(id=descriptor['id'],title=(descriptor.get('title') if descriptor.get('title') not in (None,'',descriptor.get('name'),path.name) else metadata_title) or descriptor.get('title') or path.name,authors=[],year=None,doi=descriptor.get('doi') or header_doi,url=descriptor.get('url',''),scope='full_text',origin='user',text=text,document_hash=sha)
    result=dict(source=source,headings=headings,warnings=warnings,sha256=sha,identity_review=exact_identity_review(source,header_end=header_end))
    if extraction is not None:result['extraction']=extraction
    return result

def _question(state,kind,messages,candidates=()):
    state.update(action='waiting_input',question=dict(id=identifier('question'),kind=kind,messages=list(messages),candidates=list(candidates)))
    state['version']+=1;return state

def prepare_sources(request,documents,provider,checkpoint,*,state=None,limits=None):
    state=deepcopy(state) if state else dict(version=1,action='input',request=deepcopy(request),sources=[],readings={},selections={},question=None)
    request=deepcopy(state['request']);documents=deepcopy(documents)
    if state.get('action')=='ready':return state
    def save():checkpoint(deepcopy(state))
    if not documents:
        available=state.get('sources') or request.get('sources',[])
        available=[_normalize_fetched_scope(s) if s.get('retrieved_url') else s for s in available]
        validated=validate_request(dict(request,sources=available,optional_reference_reads=True,allow_limited_delivery=True,max_reference_reads=3 if request.get('network_allowed') else 0))
        reply=prepare_evidence(validated,provider,candidates=state.get('candidates'),confirmed_candidate_id=state.get('confirmed_candidate_id'))
        if reply.evidence:
            for key in ('analysis_contracts','analysis_contract_failure'):
                if reply.evidence.get(key):state[key]=deepcopy(reply.evidence[key])
        if reply.evidence and reply.evidence.get('sources') is not None:state['sources']=deepcopy(reply.evidence['sources'])
        if reply.action=='ask_for_literature':
            _question(state,'literature',reply.questions);save();return state
        if reply.action in {'confirm_concept','needs_disambiguation'}:
            _question(state,'concept' if reply.candidates else 'scope',reply.questions,reply.candidates);state['candidates']=reply.candidates;save();return state
        if reply.action!='ready_for_explanation':
            state.update(action='needs_sources',question=dict(id=identifier('question'),kind='sources',messages=reply.questions,candidates=[]));save();return state
        state.update(action='ready',sources=reply.evidence['sources'],evidence=reply.evidence,question=None);save();return state
    # Model use is explicitly authorized at the API boundary. This old reading flag
    # means model access, while this service's network_allowed means web retrieval.
    reading_request=dict(request,network_allowed=True,optional_reference_reads=False,max_reference_reads=0)
    # Check the complete upload set before the first billable reading request.
    for doc in documents:
        if doc['source']['scope']=='full_text':
            if not body_sections(doc['source']['text'],doc.get('headings') or []):
                raise OnlineError('source_needs_structure','文献章节结构不足，尚未开始模型阅读；请补充可识别的正文。')
            # Verify the complete set's exact offsets, not just its title labels.
            create_reading_state(reading_request,doc['source'],doc['headings'],max_calls=0,identity_review=doc.get('identity_review'))
    selected=[];source_set=_source_set_context(documents) if len(documents)>1 else None
    for doc in documents:
        source=doc['source'];sid=source['id']
        if source['scope']!='full_text':selected.append(source);continue
        if not doc.get('headings'):raise OnlineError('source_needs_structure','原文尚缺可核对章节。')
        if sid not in state['readings']:
            if limits is None:raise OnlineError('invalid_config','整篇阅读必须提供显式调用限制。')
            review=doc.get('identity_review') if 'identity_review' in doc else exact_identity_review(source)
            state['readings'][sid]=create_reading_state(reading_request,source,doc['headings'],max_calls=limits.max_job_calls,identity_review=review)
            save()
        reading=state['readings'][sid]
        if source_set is not None:reading['source_set_context']=deepcopy(source_set)
        # Persisted responses may be reused by BudgetedProvider after a crash. The
        # section reservation remains owned by the durable provider, not reset calls.
        if reading['status'] in {'in_flight','failed_requires_review'}:
            reading['status']='reading';reading['reserved_calls']=reading['next_section']
        while reading['next_section']<len(reading['sections']):
            before=reading['next_section']
            section=reading['sections'][before]
            bibliography=heading_role(section['title'])=='bibliography'
            if bibliography:
                reading['readings'].append(dict(section_id=section['id'],title=section['title'],mode='local_catalogue',claims=[],reading_notes=[],key_conditions=[],reference_candidates=[],reported_gaps=[],rolling_summary=reading['rolling_summary'],catalogue=dict(source_id=sid,start=section['start'],end=section['end'],semantic_reading=False)))
                reading['next_section']+=1
                reading['status']='read_all_requires_review' if reading['next_section']==len(reading['sections']) else 'reading'
                save();continue
            read_next_section(reading,reading_request,source,provider,checkpoint=lambda _:save(),context_limit=64000)
            if reading['status']=='needs_disambiguation':
                _question(state,'scope',reading.get('questions',[]));save();return state
            if reading['next_section']==before:raise OnlineError('reading_paused','本节超出可读取范围，需要补充清晰的小节材料。')
        if sid not in state['selections']:
            choice=dict(stage='selection',reading=reading)
            try:select_evidence(choice,dict(request=request,source=source),provider,lambda _:None)
            except JobError as error:
                if error.code!='no_relevant_evidence':raise
                state['selections'][sid]=dict(status='no_relevant_evidence',source_hash=reading['source_hash']);save();continue
            chosen=choice['selected_source'];mapping=choice['source_mapping']
            for sec in reading['sections']:
                if heading_role(sec['title'])=='bibliography':
                    start=len(chosen['text']);chosen['text']+='\n\n'+source['text'][sec['start']:sec['end']]
                    chosen.setdefault('locator_only_ranges',[]).append(dict(start=start,end=len(chosen['text'])))
            if len(chosen['text'])>60000:raise OnlineError('source_too_large','选定证据及引文目录超过上下文范围，未截断。')
            state['selections'][sid]=dict(source=chosen,mapping=mapping);save()
        if state['selections'][sid].get('status')!='no_relevant_evidence':selected.append(state['selections'][sid]['source'])
    if not selected:
        _question(state,'sources',['已读正文未选出支持该术语的证据。请补充直接讨论该术语的文献，或澄清想解释的含义。']);save();return state
    if sum(len(s['text']) for s in selected)>120000:raise OnlineError('source_too_large','多篇证据超过上下文限制，未截断。')
    combined=dict(request,sources=selected,optional_reference_reads=True,allow_limited_delivery=True,max_reference_reads=3 if request.get('network_allowed') else 0)
    reply=prepare_evidence(validate_request(combined),provider)
    if reply.evidence and reply.evidence.get('reference_repair'):
        state['reference_repair']=deepcopy(reply.evidence['reference_repair']);save()
    if reply.evidence and reply.evidence.get('analysis_contracts'):
        state['analysis_contracts']=deepcopy(reply.evidence['analysis_contracts']);save()
    if reply.evidence and reply.evidence.get('analysis_contract_failure'):
        state['analysis_contract_failure']=deepcopy(reply.evidence['analysis_contract_failure']);save()
    if reply.action!='ready_for_explanation':
        _question(state,'scope' if reply.action=='needs_disambiguation' else 'sources',reply.questions)
        state['sources']=reply.evidence['sources'] if reply.evidence else selected;save();return state
    state.update(action='ready',sources=reply.evidence['sources'],evidence=reply.evidence,question=None);save();return state

def apply_answer(decision,answer,expected_version):
    state=deepcopy(decision);question=state.get('question')
    if state['version']!=expected_version or not question or answer.get('question_id')!=question['id']:
        raise OnlineError('stale_question','问题已更新，请重新读取。',409)
    if set(answer)-{'question_id','action','candidate_id','explanation','allow_network'}:raise OnlineError('invalid_answer','回答含不支持字段。')
    if 'allow_network' in answer:
        if type(answer['allow_network']) is not bool or answer.get('action')!='continue' or question['kind'] not in {'literature','sources'}:raise OnlineError('invalid_answer','联网授权需要明确确认。')
        state['request']['network_allowed']=answer['allow_network']
    if answer.get('action')=='resume_sources':state['request']['literature_prompted']=True
    elif answer.get('action')=='clarify':
        explanation=answer.get('explanation')
        if not isinstance(explanation,str) or not 1<=len(explanation.strip())<=1200:raise OnlineError('invalid_answer','请填写简短、明确的补充问题。')
        state['request']['question']=(state['request'].get('question','')+'\n用户补充：'+explanation.strip()).strip()
        validate_request(state['request']);state['readings']={};state['selections']={};state.pop('candidates',None);state.pop('confirmed_candidate_id',None)
    elif question['kind'] in {'literature','sources'} and answer.get('action')=='continue':
        state['request']['literature_prompted']=True
        if question['kind']=='sources' and state['request'].get('network_allowed'):
            # Explicit search-again differs from clarifying the same acquired text.
            # Retain the acquisition for audit but stop presenting it as active.
            state.setdefault('acquisition_history',[]).append(dict(sources=deepcopy(state.get('sources',[])),candidates=deepcopy(state.get('candidates',[]))))
            state['sources']=[];state['request']['sources']=[]
            state.pop('candidates',None);state.pop('confirmed_candidate_id',None)
    elif question['kind']=='concept':
        key=answer.get('candidate_id')
        if key not in {c['id'] for c in question['candidates']}:raise OnlineError('invalid_answer','请确认列表中实际存在的概念。')
        state['confirmed_candidate_id']=key
    else:raise OnlineError('needs_sources','请补充资料或明确目标定义后再继续。')
    state.update(action='input',question=None,version=state['version']+1);return state
