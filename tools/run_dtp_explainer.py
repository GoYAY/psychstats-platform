"""One start for the already supplied DTP paper; no embedded credentials."""
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tools.run_term_explainer import main

if __name__=='__main__':
    root=Path(__file__).resolve().parents[1]
    folder=root/'.superpowers/sdd/2026-10-18-personal-term-explainer-phase1/live/dtp-user-pdf'
    arguments=['--input',str(folder/'section-input-round2.json'),
        '--seed',str(folder/'section-state-round2.json'),'--output',str(folder/'dtp-complete-run')]
    if '--live' in sys.argv[1:]: arguments+=['--live','--run-to-completion','--send-selected-sources','--open']
    raise SystemExit(main(arguments))
