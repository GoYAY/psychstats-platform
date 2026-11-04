"""One-off, source-reviewed DTP Appendix recovery. Offline; never accesses keys."""
from pathlib import Path
import argparse
import json
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from term_explainer.full_job import fingerprint
from term_explainer.reconciliation import apply_section_scope_review
from tools.read_term_sections import atomic_write,load_json
from tools.run_term_explainer import summary


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply',action='store_true')
    args=parser.parse_args(argv)
    root=Path(__file__).resolve().parents[1]
    folder=root/'.superpowers/sdd/2026-10-18-personal-term-explainer-phase1/live/dtp-user-pdf/dtp-complete-run'
    lock=None; lock_path=folder/'job.lock'
    try:
        if args.apply: lock=lock_path.open('x',encoding='utf-8')
        state=load_json(folder/'job.json',16777216)
        payload=load_json(folder/'input.json')
        digest='cff8f2dd70e57a73ed03ec40b13a9c7ecc282f6b0a0885655144dfb1beb91688'
        if any(r.get('request_hash')==digest for r in state.get('reconciliations',[])):
            print(json.dumps(dict(already_reconciled=True,api_calls=0,progress=summary(state)),ensure_ascii=False,indent=2))
            return 0
        response=load_json(folder/'responses'/(digest+'.json'),16777216)
        source=payload['source']; text=source['text']
        passages=[
            'The Thurstonian item response theory (TIRT) model is a dominance model',
            'The Zinnes and Griggs Pairwise Preference model (ZG-MUPP; Joo et al., 2021) is',
        ]
        refs=[]
        for passage in passages:
            start=text.index(passage,text.index('Appendix'))
            refs.append(dict(source_id=source['id'],start=start,end=start+len(passage)))
        conflicts=json.loads(response['reply']['content'])['anchor_conflicts']
        review=dict(decision='section_scope_not_anchor_conflict',reviewer='codex_local_source_review',
            reason='已对照用户PDF提取原文：本附录分别介绍TIRT与ZG-MUPP，是同篇论文的比较模型背景；正文DTP方法已在先前小节读取。附录不重复DTP定义不构成用户术语/文献身份冲突。保留比较方法的归属，不把它们当作DTP专属属性。此决定仅重分类该范围观察，不认证模型所有技术陈述。',
            source_hash=state['reading']['source_hash'],term_hash=state['reading']['term_hash'],
            section_id='section-021',request_hash=digest,response_hash=fingerprint(response),
            dismissed_conflicts=conflicts,evidence=refs)
        new=apply_section_scope_review(state,payload,response,review)
        if args.apply:
            audit=folder/'reconciliation'; audit.mkdir(exist_ok=True)
            backup=audit/'appendix-scope-original-job.json'
            if backup.exists() and fingerprint(load_json(backup,16777216))!=fingerprint(state):
                raise ValueError('Existing reconciliation backup differs; not overwritten')
            if not backup.exists(): atomic_write(backup,state)
            atomic_write(audit/'appendix-scope-review.json',review)
            atomic_write(folder/'job.json',new)
            atomic_write(folder/'report.json',summary(new))
        print(json.dumps(dict(applied=args.apply,api_calls=0,progress=summary(new)),ensure_ascii=False,indent=2))
        return 0
    except (ValueError,KeyError,TypeError,OSError) as error:
        print(json.dumps(dict(error='reconciliation_not_applied',message=str(error)),ensure_ascii=False),file=sys.stderr)
        return 2
    finally:
        if lock is not None:
            lock.close(); lock_path.unlink()


if __name__=='__main__': raise SystemExit(main())
