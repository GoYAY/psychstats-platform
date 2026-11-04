"""Evidence-bound display metadata; immutable user anchors remain untouched."""
from copy import deepcopy
import re
from .evidence import resolve_reference


def verified_identity(term,proposal,sources):
    if term.get('en','').strip() or proposal is None:return None
    if not isinstance(proposal,dict) or set(proposal)!={'en','refs'}:raise ValueError('invalid identity metadata')
    english=proposal['en']
    if not isinstance(english,str) or not 2<=len(english.strip())<=160 or not re.search('[A-Za-z]',english):
        raise ValueError('invalid source English name')
    refs=proposal['refs']
    if not isinstance(refs,list) or not 1<=len(refs)<=3:raise ValueError('English name needs source support')
    positions=[resolve_reference(ref,sources) for ref in refs]
    by_id={s['id']:s for s in sources}
    if not any(re.search(r'(?<![A-Za-z0-9])'+re.escape(english.strip())+r'(?![A-Za-z0-9])',
                         by_id[p['source_id']]['text'][p['start']:p['end']],re.I) for p in positions):
        raise ValueError('English name is absent from provided evidence')
    return dict(en=english.strip(),refs=positions,basis='source_located_model_mapping')
