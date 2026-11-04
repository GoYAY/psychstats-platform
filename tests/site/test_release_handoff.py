import hashlib,json,tempfile,unittest,zipfile
from pathlib import Path
from tools.package_online_release import package_release

class HandoffTests(unittest.TestCase):
    def test_manifest_is_verified_and_only_allowlisted_backend_is_packaged(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);release=root/'release';release.mkdir();(release/'index.html').write_text('public')
            manifest=dict(releaseId='test-release',resources=[dict(path='index.html',sha256=hashlib.sha256(b'public').hexdigest(),bytes=6)])
            (release/'release-manifest.json').write_text(json.dumps(manifest))
            app=root/'term_explainer';app.mkdir();(app/'__init__.py').write_text('')
            (app/'.env').write_text('DO_NOT_SHIP');(app/'raw.pdf').write_bytes(b'private');(app/'fixtures').mkdir();(app/'fixtures/private.json').write_text('private')
            tools=root/'tools';tools.mkdir()
            for name in ('serve_term_generation.py','term_generation_worker.py','manage_term_invites.py','requirements-term-generation.lock','requirements-term-generation.in'):(tools/name).write_text('# runtime')
            deploy=root/'deploy';deploy.mkdir();(deploy/'term-generation.env.example').write_text('DEEPSEEK_API_KEY=\n')
            (deploy/'figure-qa-manifest.json').write_text(json.dumps({'sha256':{}}))
            output=root/'handoff';result=package_release(root,release,output,qa_dir=root)
            with zipfile.ZipFile(output/'backend.zip') as archive:
                names=archive.namelist();self.assertIn('term_explainer/__init__.py',names);self.assertFalse(any('fixtures' in n or n.endswith(('.pdf','.env')) for n in names))
            with zipfile.ZipFile(output/'static.zip') as archive:self.assertEqual(set(archive.namelist()),{'index.html','release-manifest.json'})
            self.assertEqual(result['releaseId'],'test-release')
            self.assertEqual(len(result['backendId']),20)
            with self.assertRaises(FileExistsError):package_release(root,release,output,qa_dir=root)
            (release/'index.html').write_text('tampered')
            with self.assertRaisesRegex(ValueError,'hash'):package_release(root,release,root/'second',qa_dir=root)
            self.assertFalse((root/'second').exists())
            (release/'index.html').write_text('public')
            (deploy/'figure-qa-manifest.json').write_text(json.dumps({'sha256':{},'requireRuntimeNotices':True}))
            with self.assertRaisesRegex(ValueError,'license'):
                package_release(root,release,root/'missing-notices',qa_dir=root)
            self.assertFalse((root/'missing-notices').exists())
