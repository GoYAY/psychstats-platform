"""Package explicit accepted artefacts; never invokes generation or searches folders."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from term_explainer.library_export import export_package

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('request','lesson','sources','figures','output'):parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--term-id',required=True);parser.add_argument('--original',action='append',default=[])
    args=parser.parse_args();load=lambda p:json.loads(p.read_text(encoding='utf-8'))
    originals={}
    for value in args.original:
        if '=' not in value:parser.error('--original expects SOURCE_ID=PATH')
        key,path=value.split('=',1)
        if key in originals:parser.error('Duplicate source ID in --original')
        originals[key]=Path(path)
    print(json.dumps(export_package(load(args.request),load(args.lesson),sources=load(args.sources),figures={k:Path(v) for k,v in load(args.figures).items()},originals=originals,term_id=args.term_id,output=args.output),ensure_ascii=False,indent=2))

if __name__=='__main__':main()
