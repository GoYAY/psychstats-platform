"""Offline reading-cost accounting for the merged reading plan.

Zero model calls: builds the reading plan for a real PDF and compares the new
unit layout against the original per-section traversal in characters only.
Also exports a per-stage cost summary from an existing jobs ledger.
"""
import argparse,json,sys
from pathlib import Path


def build_report(pdf_path,descriptor_id=None):
    root=Path(__file__).resolve().parents[1]
    sys.path.insert(0,str(root))
    from term_explainer.online.sources import parse_source
    from term_explainer.online.config import load_config
    from term_explainer.section_reading import create_reading_state
    from term_explainer.reading_plan import PLAN_VERSION
    import tempfile
    from tests.term_explainer.online.helpers import environment
    cfg=load_config(environment(tempfile.mkdtemp()))
    pdf=Path(pdf_path)
    doc=parse_source(pdf,dict(id=descriptor_id or "source-probe",name=pdf.name,title=pdf.name,mime="application/pdf"),cfg.limits)
    source=doc["source"];text=source["text"]
    request=dict(request_id="cost-probe",term=dict(id="t",zh="探针",en="",aliases=[],definition=""),
        question="cost probe",sources=[source],catalog=[],known_terms=[],
        literature_prompted=True,network_allowed=False,max_reference_reads=0)
    state=create_reading_state(request,source,doc["headings"],max_calls=999)
    sections=state["section_index"];units=state["sections"]
    body_sections=[s for s in sections if s.get("role")!="bibliography"]
    body_units=[u for u in units if u.get("role")=="body"]
    from term_explainer.pipeline import ANALYSIS_PROMPT
    contract_chars=len(ANALYSIS_PROMPT)
    old_calls=len(body_sections);new_calls=len(body_units)
    return dict(pdf=pdf.name,chars=len(text),plan_version=PLAN_VERSION,
        original_sections=len(sections),body_sections=len(body_sections),
        reading_units=len(units),body_units=len(body_units),
        merged_units=sum(1 for u in units if u.get("merged")),
        max_unit_chars=max((u["chars"] for u in units),default=0),
        min_unit_chars=min((u["chars"] for u in units),default=0),
        unit_chars=[u["chars"] for u in units],
        unit_section_counts=[len(u["section_ids"]) for u in units],
        old_reading_calls=old_calls,new_reading_calls=new_calls,
        call_reduction_pct=round(100*(old_calls-new_calls)/max(old_calls,1),1),
        old_repeat_contract_chars=old_calls*contract_chars,
        new_repeat_contract_chars=new_calls*contract_chars,
        new_memory_chars_cap=6800,
        note="字符级离线对比，不折算 token 或缓存命中；实际以新任务回执为准")


def summarize(db_path,job_id=None):
    import sqlite3
    con=sqlite3.connect("file:%s?mode=ro"%db_path,uri=True)
    where="" if not job_id else "where job_id=?"
    params=() if not job_id else (job_id,)
    rows=[(r[0],r[1],r[2],r[3],r[4]) for r in con.execute(
        "select job_id,operation,state,day,reserved_tokens from provider_calls %s"%where,params)]
    audits=[(r[0],json.loads(r[1])) for r in con.execute(
        "select job_id,body from audit %s"%where,params)]
    by_day={}
    for job,operation,state,day,tokens in rows:
        by_day["%s:calls"%day]=by_day.get("%s:calls"%day,0)+1
        by_day["%s:tokens"%day]=by_day.get("%s:tokens"%day,0)+tokens
    stage={}
    for job,body in audits:
        s=body.get("stage");stage.setdefault(s,{"calls":0,"tokens":0})
        stage[s]["calls"]+=body.get("calls") or 1
        stage[s]["tokens"]+=body.get("total_tokens") or 0
    return dict(scope=job_id or "all",provider_calls=len(rows),
        tokens=sum(r[4] for r in rows),
        by_day=dict(sorted(by_day.items())),by_stage=stage)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest="command",required=True)
    plan=sub.add_parser("plan",help="offline plan comparison for one PDF")
    plan.add_argument("--pdf",type=Path,required=True)
    plan.add_argument("--out",type=Path,required=True)
    plan.add_argument("--descriptor-id",default=None)
    summ=sub.add_parser("summarize",help="export stage cost summary from a jobs ledger")
    summ.add_argument("--db",required=True)
    summ.add_argument("--job-id",default=None)
    summ.add_argument("--out",type=Path,required=True)
    args=parser.parse_args()
    if args.command=="plan":
        report=build_report(args.pdf,args.descriptor_id)
        args.out.parent.mkdir(parents=True,exist_ok=True)
        args.out.write_text(json.dumps(report,ensure_ascii=False,indent=1),encoding="utf-8")
        print(json.dumps({k:v for k,v in report.items() if not isinstance(v,list)},ensure_ascii=False,indent=1))
    elif args.command=="summarize":
        report=summarize(args.db,args.job_id)
        args.out.parent.mkdir(parents=True,exist_ok=True)
        args.out.write_text(json.dumps(report,ensure_ascii=False,indent=1),encoding="utf-8")
        print(json.dumps(report,ensure_ascii=False,indent=1))


if __name__=="__main__":
    main()
