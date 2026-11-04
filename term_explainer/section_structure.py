"""Section-name matching without rewriting document text or evidence offsets."""
import re

NUMBERED=re.compile(r'^(?P<number>[1-9][0-9]?(?:\.[0-9]{1,2})*)[.)]?(?P<gap>\s+)(?P<label>[A-Za-z\u4e00-\u9fff].{0,99})$')
STANDARD={'abstract','摘要','introduction','引言','前言','method','methods','方法','研究方法',
          'result','results','结果','研究结果','discussion','讨论','conclusion','conclusions',
          '结论','references','参考文献','appendix','附录'}


def heading_role(title):
    value=re.sub(r'^#{1,6}\s*','',title.strip())
    value=re.sub(r'^\d+(?:\.\d+)*[.)]?\s+','',value)
    value=re.sub(r'\s+','',value).casefold().rstrip(':：')
    if value in {'abstract','摘要'}:return 'abstract'
    if value in {'references','参考文献'}:return 'bibliography'
    return 'body'


def explicit_heading(label):
    """Return the ORIGINAL heading prefix, including intra-word spacing."""
    compact=re.sub(r'\s+','',label).casefold().rstrip(':：')
    if compact in STANDARD:return label
    # A run-in Chinese abstract is a real boundary, not a renamed paragraph.
    match=re.match(r'^(摘\s*要)(?:\s{2,}|\s*[:：]\s*)(?=\S)',label)
    if match:return match[1]
    numbered=NUMBERED.fullmatch(label)
    if numbered and not re.search(r'[。！？!?;；,，()（）=<>]',numbered['label']):
        # Separate numeric cells are table content, not a section suffix.
        if re.search(r'\s{2,}[+\-−]?(?:\d+(?:\.\d+)?|\.\d+)(?:[eE][+\-]?\d+)?[%％]?\*{0,3}\s*$',numbered['label']):return None
        if '.' in numbered['number'] or len(numbered['gap'])>=2 or re.sub(r'\s+','',numbered['label']).casefold() in STANDARD:
            return label
    return None


def body_sections(text,headings):
    """Named non-summary/non-bibliography units with actual following content."""
    return [h for i,h in enumerate(headings)
        if h.get('role')!='front_matter' and heading_role(h['title'])=='body' and text[h['start']+len(h['title']):headings[i+1]['start'] if i+1<len(headings) else len(text)].strip()]
