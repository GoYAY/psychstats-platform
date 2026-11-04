import importlib
import json
from pathlib import Path
import tempfile
import unittest
import zipfile
from .helpers import request_payload,result_payload

class LibraryExportTests(unittest.TestCase):
    def test_same_filename_without_identity_does_not_merge_different_papers(self):
        from copy import deepcopy
        with tempfile.TemporaryDirectory() as d:
            sources=request_payload()['sources'];sources[0]['title']='paper.pdf'
            second=deepcopy(sources[0]);second.update(id='s2',text='A genuinely different uploaded paper.');sources.append(second)
            self.export(Path(d),sources=sources)
            with zipfile.ZipFile(Path(d)/'case.zip') as z:self.assertEqual(len(json.loads(z.read('library.json'))['works']),2)

    def test_utf8_original_is_preserved_as_text_not_mislabeled_pdf(self):
        with tempfile.TemporaryDirectory() as d:
            folder=Path(d);original=folder/'paper.txt';raw='原始文字材料\n'.encode('utf-8');original.write_bytes(raw)
            self.export(folder,originals={'s1':original})
            with zipfile.ZipFile(folder/'case.zip') as z:
                names=[n for n in z.namelist() if n.startswith('originals/')]
                self.assertEqual(len(names),1);self.assertTrue(names[0].endswith('.txt'));self.assertEqual(z.read(names[0]),raw)

    def test_camel_case_credentials_are_rejected_before_archive_creation(self):
        with tempfile.TemporaryDirectory() as d:
            request=request_payload();lesson=result_payload();lesson['provenance']['accessToken']='synthetic-test-token'
            with self.assertRaises(ValueError):self.exporter().export_package(request,lesson,sources=request['sources'],originals={},figures={},term_id='sample',output=Path(d)/'bad.zip')
            self.assertFalse((Path(d)/'bad.zip').exists())
    def test_public_catalogue_only_contains_existing_official_pages(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);(root/'assets/data').mkdir(parents=True);(root/'terms').mkdir()
            (root/'assets/data/search-index.json').write_text(json.dumps([{'id':'variable','zh':'变量'},{'id':'absent','zh':'缺页'}]),encoding='utf-8')
            (root/'terms/variable.html').write_text('public',encoding='utf-8')
            method=getattr(self.exporter(),'public_catalogue',None)
            self.assertTrue(callable(method),'Public catalogue exporter missing')
            data=method(root)
            self.assertEqual([t['id'] for t in data['terms']],['variable'])
            self.assertTrue(data['terms'][0]['published'])
    def exporter(self):
        try:return importlib.import_module('term_explainer.library_export')
        except ModuleNotFoundError:self.fail('The personal-library exporter is not implemented')

    def export(self,folder,*,sources=None,originals=None):
        request=request_payload();lesson=result_payload()
        lesson['provenance']={'human_scientific_review':'pending','automatic_generation_passed':False}
        return self.exporter().export_package(request,lesson,sources=sources or request['sources'],originals=originals or {},figures={},term_id='population-and-sample',output=folder/'case.zip')

    def test_export_preserves_user_anchor_and_review_provenance(self):
        with tempfile.TemporaryDirectory() as d:
            folder=Path(d);report=self.export(folder)
            with zipfile.ZipFile(folder/'case.zip') as z:
                package=json.loads(z.read('library.json'))
                self.assertEqual(package['terms'][0]['anchor']['definition'],'想研究的人与实际调查到的人。')
                self.assertFalse(package['revisions'][0]['lesson']['provenance']['automatic_generation_passed'])
                self.assertEqual(package['sources'][0]['originalStatus'],'missing')
                self.assertEqual(report['terms'],1)

    def test_two_identical_originals_share_hash_but_distinct_versions_do_not(self):
        with tempfile.TemporaryDirectory() as d:
            folder=Path(d);a=folder/'a.pdf';b=folder/'b.pdf';a.write_bytes(b'%PDF-1.7\nshared');b.write_bytes(a.read_bytes())
            sources=request_payload()['sources'];sources.append(dict(sources[0],id='s2'))
            self.export(folder,sources=sources,originals={'s1':a,'s2':b})
            with zipfile.ZipFile(folder/'case.zip') as z:
                package=json.loads(z.read('library.json'));originals=[n for n in z.namelist() if n.startswith('originals/')]
                self.assertEqual(len(originals),1)
                self.assertEqual(len({s['blobHash'] for s in package['sources']}),1)
            b.write_bytes(b'%PDF-1.7\ndifferent')
            self.export(folder,sources=sources,originals={'s1':a,'s2':b})
            with zipfile.ZipFile(folder/'case.zip') as z:self.assertEqual(len([n for n in z.namelist() if n.startswith('originals/')]),2)

    def test_no_environment_or_job_logs_exported(self):
        with tempfile.TemporaryDirectory() as d:
            folder=Path(d);(folder/'.env').write_text('secret-never-export');(folder/'job.log').write_text('private-unselected-log')
            self.export(folder)
            with zipfile.ZipFile(folder/'case.zip') as z:
                self.assertNotIn('.env',z.namelist());self.assertNotIn('job.log',z.namelist())
                content=b''.join(z.read(n) for n in z.namelist())
                self.assertNotIn(b'secret-never-export',content)

    def test_repeated_export_has_stable_identity_and_verified_manifest(self):
        import hashlib
        with tempfile.TemporaryDirectory() as d:
            folder=Path(d);first=self.export(folder);second=self.export(folder)
            self.assertEqual(first['packageId'],second['packageId'])
            with zipfile.ZipFile(folder/'case.zip') as z:
                manifest=json.loads(z.read('manifest.json'))
                for item in manifest['files']:self.assertEqual(hashlib.sha256(z.read(item['path'])).hexdigest(),item['hash'])

if __name__=='__main__':unittest.main()
