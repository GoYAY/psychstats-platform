"""QA-only fixed continuation authorization, sharing the historical ledger."""
import json
from term_explainer.online.config import OnlineError
PHASE='release-readiness-2026-10-24'
CAPS=dict(modelRequests=20,networkRequests=6,tokensAccounted=400000)

def totals(store):
    with store.connection() as db:
        rows=db.execute('SELECT operation,state,reserved_tokens FROM provider_calls').fetchall()
        table=db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='live_external_verifications'").fetchone()
        external=db.execute('SELECT COUNT(*) FROM live_external_verifications').fetchone()[0] if table else 0
    return dict(modelRequests=sum(r['operation']=='generate' for r in rows),networkRequests=sum(r['operation']!='generate' for r in rows)+external,tokensAccounted=sum(r['reserved_tokens'] for r in rows),uncertainRequests=sum(r['state']=='sent' for r in rows))

def authorize_phase(store):
    with store.transaction() as db:
        db.execute('CREATE TABLE IF NOT EXISTS release_verification_phases(id TEXT PRIMARY KEY,body TEXT NOT NULL)')
        row=db.execute('SELECT body FROM release_verification_phases WHERE id=?',(PHASE,)).fetchone()
        if row:return json.loads(row['body'])
        value=dict(id=PHASE,baseline=totals(store),caps=CAPS,authorization='user-approved 20 model,6network,400000tokens; no recharge')
        db.execute('INSERT INTO release_verification_phases VALUES(?,?)',(PHASE,json.dumps(value,sort_keys=True)))
        return value

def check_phase(store):
    with store.connection() as db:
        row=db.execute('SELECT body FROM release_verification_phases WHERE id=?',(PHASE,)).fetchone()
    if row is None:raise OnlineError('budget_consent_required','本轮尚无明确预算。',403)
    auth=json.loads(row['body']);current=totals(store)
    if auth['caps']!=CAPS:raise OnlineError('invalid_budget','本轮预算记录不一致。',409)
    delta={k:current[k]-auth['baseline'][k] for k in CAPS}
    if any(not 0<=delta[k]<=CAPS[k] for k in CAPS):raise OnlineError('budget_exhausted','本轮累计预算已到上限，未继续发送。',429)
    return dict(baseline=auth['baseline'],total=current,delta=delta,caps=CAPS)

class PhaseExternal:
    supports_receipt=True
    def __init__(self,store,client):self.store=store;self.client=client;self.model=client.model
    def generate(self,**kw):check_phase(self.store);return self.client.generate(**kw)
    def search(self,**kw):check_phase(self.store);return self.client.search(**kw)
    def fetch(self,**kw):check_phase(self.store);return self.client.fetch(**kw)
