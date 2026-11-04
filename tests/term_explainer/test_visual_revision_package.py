from copy import deepcopy
import unittest
try:
    from tools.package_visual_revision import merge_revision
except ImportError:
    merge_revision = None

class RevisionPackageTest(unittest.TestCase):
    def test_preserves_old_resources_notes_and_original_status(self):
        self.assertTrue(callable(merge_revision), 'revision adapter is missing')
        old = {k: [] for k in ('terms','revisions','works','sources','evidence','edges','annotations','assets')}
        old.update(schemaVersion=1,packageId='old')
        old['terms']=[{'id':'term','currentRevisionId':'r1','tags':['mine']}]
        old['revisions']=[{'id':'r1','termId':'term'}]
        old['sources']=[{'id':'s','blobHash':'abc','originalStatus':'saved'}]
        old['annotations']=[{'id':'note','text':'my note'}]
        new=deepcopy(old);new['revisions']=[{'id':'r2','termId':'term'}]
        new['terms'][0]['currentRevisionId']='r2';new['terms'][0]['tags']=[]
        new['sources']=[{'id':'s','blobHash':None,'originalStatus':'missing'}];new['annotations']=[]
        before=deepcopy(old)
        result=merge_revision(old,new)
        self.assertEqual(old,before)
        self.assertEqual([r['id'] for r in result['revisions']],['r1','r2'])
        self.assertEqual(result['terms'][0],{'id':'term','currentRevisionId':'r2','tags':['mine']})
        self.assertEqual(result['annotations'],old['annotations'])
        self.assertEqual(result['sources'],old['sources'])

    def test_conflicting_immutable_record_rejected(self):
        self.assertTrue(callable(merge_revision), 'revision adapter is missing')
        old={k: [] for k in ('terms','revisions','works','sources','evidence','edges','annotations','assets')}
        old.update(schemaVersion=1,packageId='old');old['assets']=[{'id':'a','blobHash':'one'}]
        new=deepcopy(old);new['assets'][0]['blobHash']='two'
        with self.assertRaises(ValueError):merge_revision(old,new)
