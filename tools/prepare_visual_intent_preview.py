"""Build the isolated teaching-intent candidate only; never deploy."""
from pathlib import Path
import argparse,json,sys
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from tools.prepare_local_library_preview import prepare_preview

def prepare(baseline,output,chart_build):
    if Path(output).resolve()!=ROOT/'site/visual-intent-preview':raise ValueError('Only site/visual-intent-preview is authorized')
    return prepare_preview(baseline,output,chart_build=chart_build,visual_policy_version=1)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--baseline',type=Path,default=ROOT/'site/paper-table-audit-preview');p.add_argument('--output',type=Path,default=ROOT/'site/visual-intent-preview');p.add_argument('--chart-build',type=Path,default=ROOT/'chart_widget/dist');a=p.parse_args()
    print(json.dumps(prepare(a.baseline,a.output,a.chart_build),ensure_ascii=False,indent=2))
