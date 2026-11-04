"""Candidate/baseline/accepted bookkeeping for visual repair rounds.

Version ids are content fingerprints computed by the host; artifacts live in
per-strategy directories (delivery), and the durable version relations live in
the quality state that is checkpointed with the job.
"""
from copy import deepcopy
import hashlib,json


def candidate_id(visual):
    payload=json.dumps(visual,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()
    return "v"+hashlib.sha256(payload).hexdigest()[:16]


def version_record(visual,*,candidate,baseline,accepted,mechanical=None,review=None,strategy=None,regression=None):
    return dict(version_id=candidate_id(visual),visual=deepcopy(visual),
        candidate=candidate,baseline=baseline,accepted=accepted,
        mechanical=deepcopy(mechanical) if mechanical else None,
        review=deepcopy(review) if review else None,
        strategy=strategy,regression=regression)


def append_version(state,visual,**kwargs):
    record=version_record(visual,**kwargs)
    state.setdefault("version_log",[]).append(record)
    state["candidate_version"]=record["version_id"]
    if record["accepted"]:state["accepted_version"]=record["version_id"]
    if not state.get("baseline_version"):state["baseline_version"]=record["version_id"]
    return record


def restore_relations(state):
    """Return (candidate,baseline,accepted) from a checkpointed state; unknown
    or tampered states degrade to a fresh baseline instead of guessing."""
    log=state.get("version_log") or []
    known={r.get("version_id") for r in log if isinstance(r,dict)}
    def pick(key):
        value=state.get(key)
        return value if value in known else None
    return pick("candidate_version"),pick("baseline_version"),pick("accepted_version")
