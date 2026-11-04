"""Audit every saved case and built term; keep per-page evidence of coverage."""
import argparse
import json
from pathlib import Path
from sitegen.analysis_catalog import load_analysis_cases, select_analysis_examples
from sitegen.paper_reporting import paper_data
from tools.export_next_preview import Tree

ROOT=Path(__file__).resolve().parents[1]


def audit(output):
    cases=load_analysis_cases(ROOT/'site/content/analysis_cases')
    catalog=json.loads((ROOT/'site/content/analysis_catalog.json').read_text(encoding='utf-8'))
    routes={r['term_id']:r for r in catalog['term_routes']}
    report={'cases':[],'terms':[],'failures':[]}
    for slug,case in cases.items():
        result=json.loads((ROOT/f'site/content/analysis_results/{slug}.json').read_text(encoding='utf-8'))
        data=paper_data(case,result)
        issue=[t['name'] for t in data['tables'] if t['columns'] in (['effect','value'],['index','value'])]
        if issue:report['failures'].append({'case':slug,'verticalTables':issue})
        report['cases'].append({'id':slug,'tables':[{'name':t['name'],'columns':t['columns'],'rows':len(t['rows'])} for t in data['tables']]})
    for file in sorted((output/'terms').glob('*.html')):
        slug=file.stem;route=routes.get(slug,{})
        term=json.loads((ROOT/'site/content/drafts'/(slug+'.json')).read_text(encoding='utf-8'))
        tree=Tree(file.read_text(encoding='utf-8'))
        sections=tree.root.find(lambda n:n.attrs.get('id')=='paper-results')
        expected=select_analysis_examples(slug,route,cases) if route.get('mode')=='tutorial' and term.get('r_practice') else []
        tables=sum(len(s.find(lambda n:n.tag=='table')) for s in sections)
        entry={'id':slug,'tableCount':tables,'mainCase':expected[0]['id'] if expected else None,'mode':route.get('mode'),'hasRPractice':bool(term.get('r_practice'))}
        report['terms'].append(entry)
        if bool(sections)!=bool(expected):report['failures'].append({'term':slug,'error':'missing/unexpected paper section'})
        if expected and sections:
            links=sections[0].find(lambda n:n.tag=='a')
            if not links or links[0].attrs.get('href')!='../analyses/'+expected[0]['id']+'.html':
                report['failures'].append({'term':slug,'error':'main case mismatch'})
        for section in sections:
            for table in section.find(lambda n:n.tag=='table'):
                headers=table.find(lambda n:n.tag=='thead')[0].find(lambda n:n.tag=='th')
                if len(headers)<2:report['failures'].append({'term':slug,'error':'incomplete table headers'})
    if len(report['terms'])!=179:report['failures'].append({'error':'full glossary not audited','count':len(report['terms'])})
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    report=audit(args.output)
    target=ROOT/'logs/paper-table-audit';target.mkdir(parents=True,exist_ok=True)
    (target/'coverage.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'cases':len(report['cases']),'terms':len(report['terms']),
                      'termsWithTables':sum(t['tableCount']>0 for t in report['terms']),
                      'failures':report['failures']},ensure_ascii=False))
    raise SystemExit(bool(report['failures']))
