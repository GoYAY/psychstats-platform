"""Report actual SVG chromatic coverage, not export counts or cache timestamps."""
from pathlib import Path
import colorsys
import json
import re

ROOT=Path(__file__).resolve().parents[1]
entries={slug:entry for file in (ROOT/'site/content/plain_visuals').glob('*.json')
         for slug,entry in json.loads(file.read_text(encoding='utf-8')).items()}
diagrams=json.loads((ROOT/'site/content/diagram_samples.json').read_text(encoding='utf-8'))
rows=[]
for slug,entry in sorted(entries.items()):
    term=json.loads((ROOT/'site/content/drafts'/f'{slug}.json').read_text(encoding='utf-8'))
    if entry['decision']=='skip':
        rows.append({'slug':slug,'name':term['zh'],'status':'未配图','reason':entry['reason']})
        continue
    filename=(ROOT/'site/assets/examples-v2'/f'{slug}.svg') if entry['decision']=='draw' else None
    if filename is None:
        filename=ROOT/'site/assets/diagrams'/diagrams[entry['reuse']]['file']
    if filename is None or not filename.exists():
        raise ValueError(f'{slug}: missing figure for coverage audit')
    hues=set()
    for color in re.findall(r'#[0-9a-fA-F]{6}\b',filename.read_text(encoding='utf-8')):
        rgb=tuple(int(color[i:i+2],16)/255 for i in (1,3,5))
        h,s,v=colorsys.rgb_to_hsv(*rgb)
        if s>=0.4 and v>=0.25:
            hues.add(color.lower())
    rows.append({'slug':slug,'name':term['zh'],'kind':entry.get('kind','reuse'),
                 'status':'含辅助色' if len(hues)>=2 else '单主色',
                 'chromatic_colors':sorted(hues),
                 'source':str(filename.relative_to(ROOT)),
                 'note':'色数不证明语义正确；结合源数据与对象／状态标注人工核对。'})
summary={status:sum(r['status']==status for r in rows) for status in ('含辅助色','单主色','未配图')}
output={'summary':summary,'terms':rows}
(ROOT/'logs/figure-color-coverage.json').write_text(json.dumps(output,ensure_ascii=False,indent=2),encoding='utf-8')
lines=['# 图示配色实际覆盖清单','',
       '按最终SVG中的高饱和度色值统计，而非导出次数。含辅助色是当前状态，不等于本轮新增；色数不能替代图意审查。单主色不自动代表遗漏，也不自动代表合理，仍需结合对象与证据判断。','',
       f"目前：含辅助色{summary['含辅助色']}个，单主色{summary['单主色']}个，未配图{summary['未配图']}个。",'',
       '| 术语 | 实际状态 | 图示类型 |','| --- | --- | --- |']
labels={'story':'故事／过程','table':'表格','histogram':'频数分布','bars':'柱状图',
        'scatter':'散点图','lines':'曲线','intervals':'区间','network':'结构关系',
        'segments':'分段比较','boxplot':'箱线图','reuse':'复用已有图解'}
for row in rows:
    lines.append(f"| {row['name']} | {row['status']} | {labels.get(row.get('kind'),'暂不配图')} |")
(ROOT/'docs/figure-color-coverage.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
print(json.dumps(summary,ensure_ascii=False))
