import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from sitegen.build import build_site

ROOT = Path(__file__).resolve().parents[2]

class FavoritesTests(unittest.TestCase):
    def test_rendered_pages_expose_matching_independent_favorite_controls(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            build_site('preview', out)
            home = (out/'index.html').read_text(encoding='utf-8')
            detail = (out/'terms/p-value.html').read_text(encoding='utf-8')
            self.assertIn('data-topic-link="favorites"', home)
            self.assertIn('data-favorite="p-value"', home)
            self.assertIn('data-favorite="p-value"', detail)
            self.assertIn('id="favorite-topic-filter"', home)
            drafts = [json.loads(path.read_text(encoding='utf-8'))
                      for path in (ROOT/'site/content/drafts').glob('*.json')]
            foundation_count = sum(term['topic'] == 'foundations' for term in drafts)
            self.assertRegex(home, rf'data-topic-count="foundations"[^>]*>{foundation_count}<')
            self.assertEqual(home.count('data-favorite='), len(drafts))
            self.assertTrue((out/'assets/favorites.js').is_file())

    def test_store_survives_reload_validates_data_and_handles_denied_storage(self):
        source = ROOT/'site/assets/favorites.js'
        self.assertTrue(source.is_file(), '收藏存储模块尚未实现')
        program = r"""
const vm=require('node:vm'),fs=require('node:fs'),assert=require('node:assert/strict');
const code=fs.readFileSync(process.argv[1],'utf8');
let raw=null;
const storage={getItem:()=>raw,setItem:(key,value)=>{raw=value}};
function load(storage){let context={window:{localStorage:storage,addEventListener:()=>{}},Set,JSON};vm.runInNewContext(code,context);return context.window.PsychFavorites;}
let store=load(storage);assert.equal(store.has('p-value'),false);
assert.equal(store.toggle('p-value'),true);assert.equal(load(storage).has('p-value'),true);
assert.equal(load(storage).toggle('p-value'),false);assert.equal(load(storage).ids().length,0);
let first=load(storage),second=load(storage),notifications=0;first.subscribe(()=>{notifications++});
second.toggle('anova');first.toggle('p-value');assert.deepEqual(Array.from(load(storage).ids()),['anova','p-value']);
assert.equal(notifications,1);first.toggle('invalid id');assert.equal(notifications,1);
raw='["p-value","p-value",null,7]';assert.deepEqual(Array.from(load(storage).ids()),['p-value']);
raw='{bad';assert.equal(load(storage).ids().length,0);
let denied=load({getItem:()=>{throw Error('denied')},setItem:()=>{throw Error('denied')}});
assert.equal(denied.toggle('anova'),true);assert.equal(denied.has('anova'),true);assert.equal(denied.persistent(),false);
console.log('收藏持久化、取消、异常数据及禁用存储验证通过');
"""
        result = subprocess.run(['node', '-e', program, str(source)], capture_output=True, text=True, encoding='utf-8')
        self.assertEqual(result.returncode, 0, result.stdout+result.stderr)

if __name__ == '__main__': unittest.main()
