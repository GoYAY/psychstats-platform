"""Bounded diagram-only correction. No prose, evidence or software-code rewrite."""
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path
import json
from ..contract import validate_request,validate_result
from ..pipeline import _parse

def repair_visual(request,lesson,sources,provider,*,visual_host=None,issues=None,visual_policy_version=0,preservation=None,repair_policy_version=1):
    if type(repair_policy_version) is not int or repair_policy_version not in (1,2):raise ValueError('Unknown visual repair policy')
    contract=(Path(__file__).parents[1]/'skills/explain-research-term/references/lesson-contract.md').read_text(encoding='utf-8')
    visual_contract=contract[contract.index('visual 为'):contract.index('quiz 为')]
    old=lesson['visual'];indexed={s['id']:s for s in sources};snippets=[]
    for ref in old.get('refs',[]):
        source=indexed[ref['source_id']]
        snippets.append(dict(source_id=source['id'],start=ref['start'],end=ref['end'],text=source['text'][ref['start']:ref['end']]))
    visual_policy=(Path(__file__).parents[1]/'skills/explain-research-term/references/instant-visuals.md').read_text(encoding='utf-8')
    prompt='''只输出JSON对象 {"visual":{...}}。修正一份已生成科普的图示，正文、定义和问题均保持不变，不重新阅读全文。
依据输入issues逐条修正图示；可能是绘图碰撞，也可能是教学表达或呈现意图问题。用受控布局表达一个具体可观察的教学例子；只减少纯装饰元素，不得删除或合并承载教学过程的场景、对象、数值与关系，不得通过删减内容换取排版通过。若issues要求新合同适配，保留已认可的具体对象与关系，只填写相应呈现字段。
输入preservation是宿主生成的保留清单：已有场景、对象、数值、关系与refs必须逐项保留；评审点名的对象允许定向改写措辞或状态，其余一律不动；新增场景或对象须与issues一致。
关注前后变化、比较数量或可核对的行为，图为主体；虚构教学记录须标明origin=teaching，不冒充原文实测结果或自造量表阈值。
资料支持跨轮反馈时优先feedback_trace；计分匹配可用pairwise_match；其他概念选择合适的简单故事/数据图，不强套模板。
只能用提供的真实内容解释机制；保留原refs，不新增文献或科学结论。不输出代码、HTML或SVG。
'''
    from ..visual_host import visual_host_capabilities
    context=dict(term=request['term'],plain_explanation=[b for b in lesson['blocks'] if b['id'] in ('plain_explanation','detailed_explanation')],old_visual=old,evidence=snippets,
        visual_host=visual_host_capabilities(visual_host,policy_version=visual_policy_version),visual_policy_version=visual_policy_version,
        issues=issues or ['Rendered text/arrow collision requires correction'],preservation=preservation)
    if repair_policy_version==2:
        prompt+='''\n措辞修订权限：只依据宿主preservation.authorized中的精确路径修改。/title、/takeaway、/alt若被点名，可定向补充教学示例或适用范围等限定；未点名的措辞字段逐字保留。不得自增授权路径。/payload/scenes等集合路径不授权改标题。措辞授权不允许修改kind、origin、refs、presentation、教学数值或关系；其余对象沿用具体对象授权。完成修订后仍需教学复核，不得以增加限定替代必要过程图示。\n'''
        context['repair_policy_version']=2
    reply=provider.generate([dict(role='system',content=prompt+visual_contract+'\n'+visual_policy),dict(role='user',content=json.dumps(context,ensure_ascii=False))])
    value=_parse(reply)
    if set(value)!={'visual'} or not isinstance(value['visual'],dict):raise ValueError('Visual repair must change only the visual')
    if value['visual'].get('refs',[])!=old.get('refs',[]):raise ValueError('Visual repair must preserve original references')
    from ..visual_presentation import validate_presentation
    validate_presentation(value['visual'],required=visual_policy_version==1)
    revised=deepcopy(lesson);revised['visual']=value['visual']
    revised.setdefault('provenance',{})['visual_logic_review']='automatic_repair_pending_human'
    return asdict(validate_result(revised,validate_request(dict(request,sources=sources))))
