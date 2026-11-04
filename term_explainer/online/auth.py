"""Opaque invitations and sessions; callers must add Origin and CSRF checks."""
from dataclasses import dataclass
import hashlib,hmac,secrets,time
from .config import OnlineError
from .store import identifier

def hashed(value):return hashlib.sha256(value.encode()).hexdigest()

@dataclass(frozen=True)
class Session:
    owner_id:str
    token:str
    csrf:str
    expires_at:float

class InviteAuth:
    def __init__(self,store,config,*,clock=time.time):self.store=store;self.config=config;self.clock=clock

    def create_invite(self,label,*,expires_at=None):
        if not isinstance(label,str) or not 1<=len(label)<=100:raise OnlineError('invalid_request','邀请备注长度无效。')
        secret=secrets.token_urlsafe(32);now=self.clock();expires=expires_at if expires_at is not None else now+7*86400
        if expires<=now:raise OnlineError('invalid_request','邀请期限无效。')
        with self.store.transaction() as db:
            db.execute('INSERT INTO invites(id,hash,label,created,expires) VALUES(?,?,?,?,?)',(identifier('invite'),hashed(secret),label,now,expires))
        return secret

    def revoke_invite(self,invite_id):
        with self.store.transaction() as db:
            db.execute('UPDATE invites SET revoked=1 WHERE id=?',(invite_id,));db.execute('DELETE FROM sessions WHERE invite_id=?',(invite_id,))

    def exchange(self,secret):
        if not isinstance(secret,str) or not 1<=len(secret)<=128:raise OnlineError('unauthorized','邀请凭证无效或已过期。',401)
        with self.store.transaction() as db:
            row=db.execute('SELECT * FROM invites WHERE hash=?',(hashed(secret),)).fetchone();now=self.clock()
            if row is None or row['revoked'] or row['expires']<=now:raise OnlineError('unauthorized','邀请凭证无效或已过期。',401)
            token=secrets.token_urlsafe(32);csrf=secrets.token_urlsafe(32);expires=min(now+86400,row['expires'])
            db.execute('INSERT INTO sessions VALUES(?,?,?,?)',(hashed(token),row['id'],csrf,expires))
            return Session(row['id'],token,csrf,expires)

    def authenticate(self,cookie):
        if not isinstance(cookie,str) or not 1<=len(cookie)<=128:raise OnlineError('unauthorized','请验证内测邀请。',401)
        with self.store.connection() as db:
            row=db.execute('SELECT s.*,i.revoked,i.expires AS invite_expires FROM sessions s JOIN invites i ON i.id=s.invite_id WHERE s.hash=?',(hashed(cookie),)).fetchone()
            now=self.clock()
            if row is None or row['revoked'] or row['expires']<=now or row['invite_expires']<=now:raise OnlineError('unauthorized','会话已失效，请重新验证邀请。',401)
            return Session(row['invite_id'],cookie,row['csrf'],row['expires'])

    def logout(self,session):
        with self.store.transaction() as db:db.execute('DELETE FROM sessions WHERE hash=?',(hashed(session.token),))

    def validate_csrf(self,session,value):
        return isinstance(value,str) and hmac.compare_digest(session.csrf,value)
