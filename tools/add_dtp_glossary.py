"""Add locally source-reviewed helper terms; no model, key or network access."""
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path
import argparse
import hashlib
import json
import re
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from term_explainer.contract import validate_request,validate_result
from term_explainer.evidence import context_spans
from term_explainer.figures import FigureAssets
from term_explainer.full_job import fingerprint
from term_explainer.reader import build_preview
from tools.read_term_sections import atomic_write,load_json
from tools.run_term_explainer import summary


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--apply',action='store_true');args=parser.parse_args(argv)
    root=Path(__file__).resolve().parents[1]
    folder=root/'.superpowers/sdd/2026-10-18-personal-term-explainer-phase1/live/dtp-user-pdf/dtp-complete-run'
    lock=None; lock_path=folder/'job.lock'
    try:
        if args.apply: lock=lock_path.open('x',encoding='utf-8')
        state=load_json(folder/'job.json',16777216); payload=load_json(folder/'input.json')
        if state['stage']!='complete' or state['input_hash']!=fingerprint(payload):raise ValueError('Expected the completed, unchanged DTP task')
        original=payload['source']; text=original['text']
        if hashlib.sha256(text.encode()).hexdigest()!=state['reading']['source_hash']:raise ValueError('Original paper changed')
        selected=state['selected_source']; sources=[selected]; mapping=[]
        for name,section in [('context',state['reading']['sections'][0]),('appendix',state['reading']['sections'][-1])]:
            source=dict(original,id=original['id']+'-'+name,text=text[section['start']:section['end']],scope='excerpt',scope_basis='locally_reviewed_helper_term_context')
            sources.append(source); mapping.append(dict(source_id=source['id'],original_source_id=original['id'],start=section['start'],end=section['end']))
        def ref(which,needle):
            source=sources[which]
            match=re.search(r'\s+'.join(re.escape(w) for w in needle.split()),source['text'],re.I)
            if not match: raise ValueError('Cannot locate reviewed source phrase: '+needle)
            at=match.start()
            span=next(s for s in context_spans(source['id'],source['text']) if s['start']<=at<s['end'])
            return dict(source_id=source['id'],span_id=span['id'])
        entries=[]
        def add(key,name,explanation,which,needle,aliases=(),target=None):
            entries.append(dict(id=key,term=name,aliases=list(aliases),explanation=explanation,refs=[ref(which,needle)],target=target))
        add('mfc','多维迫选问卷','把测量不同特质的陈述放进同一组，要求受测者比较或排序，而不是给每条都打分。本页由这些相对选择估计多种特质。',1,'case of FCQs',aliases=['MFC','多维迫选','迫选问卷'])
        add('keying','键控方向','陈述所表达的倾向与目标特质的高低方向：越符合陈述代表特质越高，是正向；越符合代表特质越低，是负向。它决定参照选择的方向。',1,'positively',aliases=[])
        add('drv','优势反应向量','先把涉及目标特质的项目对按固定顺序排好，再写下该特质占优时预期的0/1选择。这列参照记录就是DRV，相当于该特质的参照卡。',0,'A key task in the DTP',aliases=['DRV'])
        add('match-probability','匹配概率','在给定特质水平时，一对陈述的实际偏好与该特质参照一致的可能性。模型用0到1之间的数表示这种可能性。',0,'probability that the observed',aliases=[])
        add('tirt','TIRT','用陈述之间的偏好，联合估计多种特质的计分模型。它直接分析“更偏好哪条陈述”；DTP分析“实际偏好是否符合特质参照”。',2,'The Thurstonian item response',aliases=['Thurstonian IRT'])
        add('dsm','DSM','本文的DSM指D计分测量方法（D-scoring method of measurement），将特质表示在0到1的D量尺上。这里用它分析实际选择与参照是否一致。',0,'D-scoring',aliases=[])
        add('via-dsm','DTP（via DSM）','DTP的D量尺计分路线：由匹配记录估计0到1之间的特质分数。分数越接近1，越接近该特质占优时的参照标准。',0,'D-scoring',aliases=['DTP (via DSM)','DTP（viaDSM）','DTP via DSM'])
        add('irt','IRT','项目反应理论，用概率模型连接个人特质、题目参数和作答表现。本文DTP的IRT路线把“是否与参照匹配”作为模型分析的表现。',0,'IRT Modeling.',aliases=['项目反应理论'])
        add('via-irt','DTP（via IRT）','DTP通过项目反应理论计分的路线：根据每对陈述是否与参照匹配来估计个人特质。所得分数位于可正可负的连续量尺。',0,'IRT Modeling.',aliases=['DTP (via IRT)','DTP（viaIRT）','DTP via IRT'])
        add('rfm2','RFM2','双参数有理函数模型，把0到1的特质位置与匹配概率联系起来。两个参数分别控制匹配概率达到0.5的位置，以及概率随特质变化的陡峭程度。',0,'item parameter for shape',aliases=['双参数有理函数模型'])
        add('two-pl','2PL','双参数逻辑模型，用一条S形曲线连接特质水平与匹配概率。两个参数分别控制曲线的位置和陡峭程度。',0,'IRT Modeling.',aliases=['双参数逻辑模型'])
        add('d-scale','D-scale','范围为0到1的特质量尺。本文把D=1设为目标特质占优的参照标准；D分数表示个人在这条量尺上的位置。',0,'D-scale, ranging',aliases=['D量尺','D分数'])
        add('logit','logit量尺','一种分数可正可负、没有固定上下限的连续量尺。本文IRT路线的特质分数采用它；这些分数不是0到1的概率。',0,'unlimited IRT scale',aliases=['IRT logit量尺','logit','logit分数'])
        add('discrimination','区分度','表示概率对特质水平变化有多敏感。在本文2PL路线中，对应αᵢ；数值越大，匹配概率在转折位置附近变化越快。',0,'discrimination in matching',aliases=['匹配区分度'])
        add('location','位置参数','在本文2PL路线中，βᵢ表示匹配概率为0.5时的特质位置。它帮助确定这对陈述的概率曲线在量尺上的位置。',0,'location on the u-scale',aliases=[])
        add('latent-trait','潜特质','不能直接读出、需要从选择表现推算的个人特质水平。例如责任感水平需要结合多次选择来估计。',0,'trait modeling',aliases=[])
        add('se','标准误','用于描述分数估计的精确程度。在相同量尺和模型条件下，标准误较小通常表示估计较精确。本文分别讨论D量尺与logit量尺的标准误。',0,'standard error of',target='standard-error')
        new=deepcopy(state);new['reader_sources']=sources;new['lesson']['glossary']=entries
        new['lesson']['provenance']['inline_glossary_review']=dict(basis='provided_paper_body_intro_and_appendix',new_api_calls=0,
            related_original_references_read=False,supporting_source_mapping=mapping,
            source_hashes={s['id']:hashlib.sha256(s['text'].encode()).hexdigest() for s in sources},human_scientific_signoff='pending',
            selection_policy='related_defined_and_needed_no_minimum',
            exclusions={'题组/项目对':'此例是直观组织单位，正文已具体示范。','正向计分/负向计分':'浅显方向由键控方向与例子说明，无需重复浮窗。',
                        'DTP规则/匹配记录':'正文与图示已直接讲解，不重复解释主术语的教学步骤。','模型估计':'此例是一般操作行为。','高度相关':'此例是程度描述，保留侧边相关系数链接。'})
        request=validate_request(dict(payload['request'],sources=sources))
        lesson=validate_result(new['lesson'],request);new['lesson']=asdict(lesson)
        if args.apply:
            audit=folder/'reconciliation';audit.mkdir(exist_ok=True)
            backup=audit/'before-inline-glossary-job.json'
            if not backup.exists():atomic_write(backup,state)
            click_backup=audit/'before-click-glossary-job.json'
            if not click_backup.exists():atomic_write(click_backup,state)
            atomic_write(folder/'lesson.json',new['lesson']);atomic_write(folder/'job.json',new)
            figdir=folder/'preview/figures'
            figures=FigureAssets(*[str(figdir/n) for n in ['figure.svg','figure-mobile.svg','figure.png','figure.pdf','figure-audit.json','figure-data.json']],lesson.visual['alt'])
            build_preview(lesson,figures,folder/'preview',sources=sources,catalog=request.catalog+request.known_terms)
            atomic_write(folder/'report.json',summary(new))
        print(json.dumps(dict(applied=args.apply,api_calls=0,helper_terms=len(entries),source_documents=1,body_and_evidence_unchanged=state['reading']==new['reading'] and state['evidence']==new['evidence']),ensure_ascii=False,indent=2))
        return 0
    except (ValueError,KeyError,TypeError,OSError,StopIteration) as error:
        print(json.dumps(dict(error='glossary_not_exported',message=str(error),api_calls=0),ensure_ascii=False),file=sys.stderr);return 2
    finally:
        if lock is not None:lock.close();lock_path.unlink()


if __name__=='__main__':raise SystemExit(main())
