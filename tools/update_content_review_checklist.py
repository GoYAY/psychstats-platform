"""Generate a human review ledger from current drafts and matching R evidence."""
import argparse
import json
from pathlib import Path
try:
    from tools.validate_review_examples import report_matches
except ImportError:
    from validate_review_examples import report_matches

ROOT = Path(__file__).resolve().parents[1]


def render_checklist(terms: list[dict], results: list[dict]) -> str:
    reports = {row['term_id']: row for row in results}
    rows = ['# 完整版逐页人工审核清单', '',
            f'{len(terms)}条内容待人工学术审核。示例执行、公式排版与自动检查不替代统计学审校；用户模板未执行。', '',
            '| 状态 | 术语 | 公式 | R示例 | 用户模板 |',
            '|---|---|---|---|---|']
    for term in terms:
        practice = term.get('r_practice')
        execution = template = '—'
        if practice:
            report = reports.get(term['id'], {})
            current = report_matches(practice, report)
            execution = '已执行通过' if current and report.get('verified') else '未验证／报告过期'
            template = '仅语法通过；未执行' if current and report.get('template_syntax_valid') else '未验证／报告过期'
        formula = '有；需人工核查' if term.get('formula',{}).get('latex') else '—'
        rows.append(f'| [ ] 待人工学术审核 | [{term["zh"]}](../site/dist/terms/{term["id"]}.html) | {formula} | {execution} | {template} |')
    return '\n'.join(rows)+'\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report',required=True)
    args = parser.parse_args()
    terms = [json.loads(path.read_text(encoding='utf-8')) for path in sorted((ROOT/'site/content/drafts').glob('*.json'))]
    report = json.loads((ROOT/args.report).read_text(encoding='utf-8'))
    (ROOT/'docs/human-review-checklist.md').write_text(render_checklist(terms,report['results']),encoding='utf-8')


if __name__ == '__main__':
    main()
