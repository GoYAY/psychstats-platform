"""Editorial learning ranks with stable prerequisite-first ordering."""
from typing import Any

def order_terms(terms: list[dict[str,Any]], topics: list[dict[str,Any]]) -> list[dict[str,Any]]:
    ranks={slug:(i,j) for i,topic in enumerate(topics) for j,slug in enumerate(topic.get('terms',[]))}
    topic_ranks={t['id']:i for i,t in enumerate(topics)}
    levels={'basic':0,'intermediate':1,'advanced':2}
    def rank(term):
        return (*ranks.get(term['id'],(topic_ranks.get(term.get('topic'),999),999)),levels.get(term.get('level'),999),term['id'])
    result=[]
    for topic in sorted({t.get('topic','') for t in terms},key=lambda x:(topic_ranks.get(x,999),x)):
        remaining={t['id']:t for t in terms if t.get('topic','')==topic}
        while remaining:
            ready=[t for t in remaining.values() if not (set((t.get('relations') or {}).get('prerequisites',[])) & remaining.keys())]
            if not ready:raise ValueError(f'{topic}: cyclic learning prerequisites')
            chosen=min(ready,key=rank);result.append(chosen);del remaining[chosen['id']]
    return result
