import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[2]

class StaticPreviewTests(unittest.TestCase):
    def test_route_resource_and_traversal(self):
        spec=importlib.util.spec_from_file_location('next_static',ROOT/'tools/preview_next_static.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            for rel in ['index.html','paths/index.html','paths/index.txt','_next/chunks/a.js']:
                path=root/rel;path.parent.mkdir(parents=True,exist_ok=True);path.write_text('fixture')
            self.assertEqual(module.resolve_path(root,'/psy-stats/paths/?x=1'),root/'paths/index.html')
            self.assertEqual(module.resolve_path(root,'/psy-stats/paths/index.txt?_rsc=abc'),root/'paths/index.txt')
            self.assertEqual(module.resolve_path(root,'/psy-stats/_next/chunks/a.js'),root/'_next/chunks/a.js')
            self.assertIsNone(module.resolve_path(root,'/psy-stats/../outside'))
            self.assertIsNone(module.resolve_path(root,'/psy-stats/%2e%2e/outside'))
            self.assertIsNone(module.resolve_path(root,'/psy-stats/missing.js'))
            self.assertEqual(module.resolve_path(root,'/psy-stats/index.html'),root/'index.html')

if __name__=='__main__':unittest.main()
