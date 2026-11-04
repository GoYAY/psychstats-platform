from term_explainer.online.config import load_config,OnlineError
from term_explainer.online.store import OnlineStore
from term_explainer.online.auth import InviteAuth
from .helpers import OnlineCase

class AuthTests(OnlineCase):
    def auth(self):
        return InviteAuth(OnlineStore(self.root/'private'/'jobs.sqlite'),load_config(self.env))

    def test_exchange_reopen_logout_and_secrets_are_hashed(self):
        auth=self.auth();secret=auth.create_invite('tester');session=auth.exchange(secret)
        self.assertGreaterEqual(len(secret),43)
        self.assertGreaterEqual(len(session.token),43)
        self.assertEqual(self.auth().authenticate(session.token).owner_id,session.owner_id)
        self.assertTrue(auth.validate_csrf(session,session.csrf))
        self.assertFalse(auth.validate_csrf(session,'wrong'))
        raw=(self.root/'private'/'jobs.sqlite').read_bytes()
        self.assertNotIn(secret.encode(),raw);self.assertNotIn(session.token.encode(),raw)
        auth.logout(session)
        with self.assertRaises(OnlineError):auth.authenticate(session.token)

    def test_invites_isolate_owners_and_revocation_invalidates_sessions(self):
        auth=self.auth();a=auth.exchange(auth.create_invite('a'));b=auth.exchange(auth.create_invite('b'))
        self.assertNotEqual(a.owner_id,b.owner_id)
        auth.revoke_invite(a.owner_id)
        with self.assertRaises(OnlineError):auth.authenticate(a.token)
        self.assertEqual(auth.authenticate(b.token).owner_id,b.owner_id)

    def test_unknown_expired_and_revoked_invites_fail_without_echo(self):
        now=[1000];auth=InviteAuth(OnlineStore(self.root/'private'/'jobs.sqlite'),load_config(self.env),clock=lambda:now[0])
        secret=auth.create_invite('short',expires_at=1010)
        now[0]=1011
        for value in [secret,'unknown']:
            with self.subTest(value=value),self.assertRaises(OnlineError) as c:auth.exchange(value)
            self.assertNotIn(value,c.exception.message)
        with self.assertRaises(OnlineError):auth.authenticate('unknown')
