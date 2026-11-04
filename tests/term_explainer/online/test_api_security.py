from dataclasses import replace
from .test_api import APIBase

class APISecurityTests(APIBase):
    def test_error_has_public_request_id_without_internal_data(self):
        reply=self.client.get('jobs')
        self.assertEqual(reply.status_code,401)
        self.assertEqual(reply.json()['requestId'],reply.headers['x-request-id'])
        self.assertNotIn(str(self.root),reply.text)

    def test_slow_body_is_timed_out_without_creating_a_job(self):
        import asyncio,httpx
        from term_explainer.online.api import create_app
        config=replace(self.config,limits=replace(self.config.limits,request_timeout=1))
        app=create_app(config,self.store,self.files,provider_enabled=True)
        h=self.login();h.update({'Idempotency-Key':'slow','Content-Type':'application/json'})
        async def slow():
            yield b'{';await asyncio.sleep(1.2);yield b'}'
        async def send():
            transport=httpx.ASGITransport(app=app,root_path=config.api_prefix.rstrip('/'))
            async with httpx.AsyncClient(transport=transport,base_url=config.origin+config.api_prefix,cookies=self.client.cookies) as client:
                return await client.post('jobs',content=slow(),headers=h)
        r=asyncio.run(send());self.assertEqual(r.status_code,408,r.text)
        with self.store.connection() as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM jobs').fetchone()[0],0)

    def test_boolean_versions_and_unbounded_draft_creation_are_rejected(self):
        from term_explainer.online.api import create_app
        from fastapi.testclient import TestClient
        config=replace(self.config,limits=replace(self.config.limits,max_queue=1))
        app=create_app(config,self.store,self.files,provider_enabled=True)
        client=TestClient(app,base_url=config.origin+config.api_prefix,root_path=config.api_prefix.rstrip('/'));self.addCleanup(client.close)
        h=self.login(client);h['Idempotency-Key']='one';job=client.post('jobs',json=self.body(),headers=h).json()
        r=client.post('jobs/'+job['id']+'/start',json={'version':True},headers=h);self.assertEqual(r.status_code,400)
        r=client.post('jobs',json=self.body(),headers={**h,'Idempotency-Key':'two'});self.assertEqual(r.status_code,429)

    def test_unauthorized_csrf_origin_and_unknown_fields_are_rejected(self):
        self.assertEqual(self.client.get('jobs').status_code,401)
        h=self.login()
        self.assertEqual(self.client.post('jobs',json=self.body(),headers=self.headers).status_code,403)
        self.assertEqual(self.client.post('jobs',json=self.body(),headers={**h,'Origin':'https://other.example'}).status_code,403)
        self.assertEqual(self.client.post('jobs',json={**self.body(),'provider_url':'https://evil.example'},headers={**h,'Idempotency-Key':'x'}).status_code,400)
        with self.store.connection() as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM jobs').fetchone()[0],0)

    def test_cookie_is_secure_httponly_strict_and_scoped(self):
        secret=self.auth.create_invite('cookie');r=self.client.post('sessions',json={'invitation':secret},headers=self.headers)
        cookie=r.headers['set-cookie']
        for value in ['Secure','HttpOnly','SameSite=strict','Path='+self.config.api_prefix]:self.assertIn(value,cookie)
        self.assertNotIn(secret,r.text)

    def test_invitation_attempts_are_limited_and_errors_do_not_echo_secrets(self):
        for _ in range(10):r=self.client.post('sessions',json={'invitation':'fake-secret'},headers=self.headers)
        self.assertEqual(r.status_code,429);self.assertNotIn('fake-secret',r.text)

    def test_bad_content_lengths_and_oversized_chunked_json_fail_closed(self):
        h=self.login();h['Idempotency-Key']='x'
        for length in ['-1','invalid']:
            r=self.client.post('jobs',content=b'{}',headers={**h,'Content-Type':'application/json','Content-Length':length})
            self.assertEqual(r.status_code,400,r.text)
        r=self.client.post('jobs',content=iter([b'a'*600000,b'b'*600000]),headers={**h,'Content-Type':'application/json'})
        self.assertEqual(r.status_code,413,r.text)
