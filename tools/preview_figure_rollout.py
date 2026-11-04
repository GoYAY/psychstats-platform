"""Read-only figure inspection sheets; does not touch site assets."""
from pathlib import Path
import json
import pymupdf
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'logs/figure-rollout'
records = json.loads((OUT / 'export-records.json').read_text(encoding='utf-8'))
groups = {
    'connections': ['parameter-and-statistic', 'parameter-and-statistic-mobile',
                    'independence-mobile', 'data-cleaning-mobile',
                    'validity-mobile', 'population-and-sample'],
    'clarity': ['continuous-variable', 'continuous-variable-mobile',
                'probability-density', 'equivalence-testing',
                'likelihood', 'validity'],
    'clarity-mobile': [slug + '-mobile' for slug in
                       ('probability-density', 'equivalence-testing', 'likelihood',
                        'validity', 'missing-data-mechanism', 'type-i-and-type-ii-errors')],
    'stories': [slug for slug, entry in records.items()
                if entry['kind'] == 'story' and not slug.endswith('-mobile')],
    'mobile': [slug + '-mobile' for slug in
               ('null-hypothesis', 'significance-level', 'cluster-analysis',
                'reliability', 'validity', 'model-identification')],
    'charts': ['central-tendency-and-dispersion', 'skewness', 'box-plot',
               'confidence-interval', 'r-squared', 'factor-extraction',
               'hlm', 'sem', 'reverse-scoring', 'covariance-matrix',
               'correlation-coefficient-glass', 'factor-number-choice-glass'],
}
for category, slugs in groups.items():
    for start in range(0, len(slugs), 6):
        batch = slugs[start:start+6]
        sheet = Image.new('RGB', (1520, 2100), 'white')
        label = ImageDraw.Draw(sheet)
        for index, slug in enumerate(batch):
            path = OUT / (slug + '.pdf')
            with pymupdf.open(path) as document:
                pix = document[0].get_pixmap(matrix=pymupdf.Matrix(1.3, 1.3), alpha=False)
                picture = Image.frombytes('RGB', [pix.width, pix.height], pix.samples)
            picture.thumbnail((740, 650))
            x, y = (index % 2)*760+10, (index//2)*700+32
            sheet.paste(picture, (x, y))
            label.text((x, y-22), slug, fill='#202020')
        file = OUT / f'inspect-{category}-{start//6+1}.png'
        sheet.save(file)
        print(file)
