"""Read-only complete-edition checks, including local file links."""
import json
from pathlib import Path
from html.parser import HTMLParser
from urllib.parse import unquote, urlsplit
ROOT=Path(__file__).resolve().parents[1]
DIST=ROOT/'site/dist'
class Links(HTMLParser):
    def __init__(self):super().__init__();self.targets=[];self.ids=set()
    def handle_starttag(self, tag, attrs):
        for key,value in attrs:
            if key in ('href','src') and value:self.targets.append(value)
            if key=='id' and value:self.ids.add(value)
errors=[]
pages=list(DIST.rglob('*.html'))
for path in pages:
    text=path.read_text(encoding='utf-8');parser=Links();parser.feed(text)
    for target in parser.targets:
        url=urlsplit(target)
        if url.scheme or url.netloc:continue
        destination=path.parent/unquote(url.path) if url.path else path
        if not destination.is_file():errors.append(f'{path.name}: {target}')
        elif url.fragment and destination.suffix=='.html':
            linked=Links();linked.feed(destination.read_text(encoding='utf-8'))
            if unquote(url.fragment) not in linked.ids:errors.append(f'{path.name}: missing anchor {target}')
    if path.parent.name=='terms':
        if text.count('class="option-feedback"')!=4:errors.append('choice explanations '+path.name)
        if text.index('class="real-question"')>text.index('操作性定义'):errors.append('question order '+path.name)
        if not any(marker in text for marker in ('class="term-flow"','class="term-visual"','class="paper-results"')):errors.append('visual '+path.name)
        if any(x in text for x in ['待补充','用于理解和应用“']):errors.append('placeholder '+path.name)
report=json.loads((DIST/'build_report.json').read_text(encoding='utf-8'))
expected_terms = len(list((ROOT/'site/content/drafts').glob('*.json')))
assert report['term_count']==expected_terms and report['question_count']==expected_terms
expected_pages = expected_terms + len(list((DIST/'topics').glob('*.html'))) + len(list(DIST.glob('*.html')))
expected_pages += len(list((ROOT/'site/content/analysis_cases').glob('*.json')))
assert len(pages)==report['page_count']==expected_pages
if errors:raise ValueError('\n'.join(errors))
print(f'{len(pages)} pages: local links, first research question, individual quiz feedback and visual paths passed.')
