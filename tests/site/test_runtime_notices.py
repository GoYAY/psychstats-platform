import tempfile
from pathlib import Path
import unittest
from tools.collect_runtime_notices import collect


class RuntimeNoticeTests(unittest.TestCase):
    def test_complete_text_and_hash_inventory_are_collected_from_installed_wheel(self):
        import hashlib,json
        from importlib.metadata import version
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);lock=root/'lock';lock.write_text('pypdf=='+version('pypdf'))
            output=root/'out';collect(lock,output)
            manifest=json.loads((output/'inventory.json').read_bytes())
            self.assertTrue(manifest['files'])
            for row in manifest['files']:
                raw=(output/row['path']).read_bytes()
                self.assertEqual(hashlib.sha256(raw).hexdigest(),row['sha256'])
            texts=[p.read_text(encoding='utf-8') for p in output.rglob('LICENSE*') if p.is_file()]
            self.assertTrue(any('Redistribution' in text for text in texts))
            with self.assertRaises(FileExistsError):collect(lock,output)
