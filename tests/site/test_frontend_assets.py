import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from sitegen.build import build_site


ROOT = Path(__file__).resolve().parents[2]
ASSETS = ROOT / "site" / "assets"


def run_node(source):
    completed = subprocess.run(
        ["node", "-e", source],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    if completed.returncode:
        raise AssertionError(completed.stderr)
    return json.loads(completed.stdout)


class FrontendAssetTests(unittest.TestCase):
    def test_site_uses_default_accent_even_when_old_palette_is_stored_or_in_url(self):
        theme_path = json.dumps(str(ASSETS / "theme.js"))
        result = run_node(f"""
          global.document = {{documentElement:{{dataset:{{theme:'violet'}}}}}};
          global.window = {{location:{{href:'file:///site/index.html?theme=amber'}},localStorage:{{getItem(){{throw Error('should not read old palette');}}}}}};
          require({theme_path});
          console.log(JSON.stringify(document.documentElement.dataset.theme));
        """)
        self.assertEqual(result, "cobalt")

    def test_dot_cursor_tracks_mouse_but_uses_native_text_cursor(self):
        cursor_path = json.dumps(str(ASSETS / "cursor.js"))
        result = run_node(f"""
          const cursor = require({cursor_path});
          const events = {{}};
          const dot = {{style:{{}},hidden:true,setAttribute(){{}}}};
          const doc = {{
            documentElement:{{classList:{{add(){{}}}}}},
            body:{{appendChild(node){{node.parentNode=this;}}}},
            querySelectorAll(){{return [];}},
            createElement(){{return dot;}},
            addEventListener(k,f){{events[k]=f;}}
          }};
          const win = {{MutationObserver:class {{observe(){{}}}},matchMedia(){{return {{matches:true}};}},addEventListener(k,f){{events[k]=f;}}}};
          cursor.initCursor(doc,win);
          events.pointermove({{clientX:12,clientY:34,target:{{closest(){{return null;}}}}}});
          const mouse = {{hidden:dot.hidden,position:dot.style.transform}};
          events.pointermove({{clientX:20,clientY:30,target:{{closest(selector){{return selector==='input, textarea, [contenteditable]' ? {{}} : null;}}}}}});
          console.log(JSON.stringify({{mouse,textHidden:dot.hidden}}));
        """)
        self.assertEqual(result, {"mouse": {"hidden": False, "position": "translate3d(12px, 34px, 0) translate(-50%, -50%)"}, "textHidden": True})

    def test_cursor_gently_enlarges_only_over_enabled_interactions(self):
        cursor_path = json.dumps(str(ASSETS / "cursor.js"))
        result = run_node(f"""
          const cursor = require({cursor_path});
          const events = {{}};
          const dot = {{style:{{}},hidden:true,setAttribute(){{}}}};
          const doc = {{documentElement:{{classList:{{add(){{}}}}}},
            body:{{appendChild(node){{node.parentNode=this;}}}},querySelectorAll(){{return [];}},createElement(){{return dot;}},
            addEventListener(k,f){{events[k]=f;}}}};
          const win = {{MutationObserver:class {{observe(){{}}}},matchMedia(){{return {{matches:true}};}},addEventListener(k,f){{events[k]=f;}}}};
          cursor.initCursor(doc,win);
          const states = [];
          for (const kind of ['link','plain','formula','disabled','practice','input','touch']) {{
            const target = {{closest(selector) {{
              if (selector === 'input, textarea, [contenteditable]') return kind==='input' ? {{}} : null;
              if (selector.includes(':disabled')) return kind==='disabled' ? {{}} : null;
              if (selector.includes('a[href]')) return ['link','formula','practice','disabled'].includes(kind) ? {{}} : null;
              return null;
            }}}};
            events.pointermove({{clientX:50,clientY:60,pointerType:kind==='touch'?'touch':'mouse',target}});
            states.push({{kind,scale:dot.className.includes('is-interactive')?'1.25':'1',hidden:dot.hidden}});
          }}
          events.blur();
          console.log(JSON.stringify({{states,blurHidden:dot.hidden}}));
        """)
        self.assertEqual(result, {'states': [
            {'kind':'link','scale':'1.25','hidden':False},
            {'kind':'plain','scale':'1','hidden':False},
            {'kind':'formula','scale':'1.25','hidden':False},
            {'kind':'disabled','scale':'1','hidden':False},
            {'kind':'practice','scale':'1.25','hidden':False},
            {'kind':'input','scale':'1','hidden':True},
            {'kind':'touch','scale':'1','hidden':True},
        ], 'blurHidden':True})

    def test_cursor_does_not_initialize_on_touch_only_devices(self):
        cursor_path = json.dumps(str(ASSETS / "cursor.js"))
        result = run_node(f"""
          const cursor = require({cursor_path});
          const doc = {{createElement(){{throw Error('Touch device must not create cursor');}}}};
          const win = {{matchMedia(){{return {{matches:false}};}}}};
          console.log(JSON.stringify(cursor.initCursor(doc,win)));
        """)
        self.assertFalse(result)

    def test_filter_menu_keyboard_navigation_wraps_and_supports_edges(self):
        menu_path = json.dumps(str(ASSETS / "filter-menu.js"))
        result = run_node(f"""
          const m = require({menu_path});
          console.log(JSON.stringify([
            m.nextIndex(2, 3, 'ArrowDown'),
            m.nextIndex(0, 3, 'ArrowUp'),
            m.nextIndex(1, 3, 'Home'),
            m.nextIndex(1, 3, 'End')
          ]));
        """)
        self.assertEqual(result, [0, 2, 0, 2])

    def test_topic_filters_work_without_topic_select_and_do_not_add_other_topic_cards(self):
        site_path = json.dumps(str(ASSETS / "site.js"))
        result = run_node(f"""
          const ids = ['level-filter','type-filter','r-filter'];
          const controls = Object.fromEntries(ids.map(id => [id, {{value:'', options:[], listeners:{{}}, appendChild(o) {{ this.options.push(o); }}, addEventListener(k, f) {{ this.listeners[k]=f; }} }}]));
          const card = {{ hidden:false, getAttribute() {{ return 'mean'; }} }};
          let enhanced = 0;
          global.document = {{
            querySelectorAll(s) {{ return s === '[data-term]' ? [card] : []; }},
            getElementById(id) {{ return controls[id] || null; }},
            createElement() {{ return {{}}; }}
          }};
          global.window = global;
          window.PsychSiteData = {{search:[{{id:'mean',topic:'foundations',level:'basic',type:'concept'}},{{id:'cfa',topic:'factor-analysis',level:'advanced',type:'method'}}]}};
          window.PsychSearch = require({json.dumps(str(ASSETS / 'search.js'))});
          window.PsychFilterMenu = {{enhance() {{ enhanced++; }} }};
          require({site_path});
          const initiallyVisible = !card.hidden;
          controls['level-filter'].value = 'advanced';
          controls['level-filter'].listeners.change();
          console.log(JSON.stringify({{enhanced,initiallyVisible,cardHidden:card.hidden}}));
        """)
        self.assertEqual(result, {"enhanced": 3, "initiallyVisible": True, "cardHidden": True})

    def test_search_normalization_aliases_r_functions_and_combined_filters(self):
        search_path = json.dumps(str(ASSETS / "search.js"))
        result = run_node(f"""
          const s = require({search_path});
          const terms = [
            {{id:'cfa', zh:'验证性因素分析', en:'Confirmatory Factor Analysis', aliases:['CFA'], search_terms:['量表结构怎么检验','lavaan cfa'], topic:'factor-analysis', level:'advanced', type:'method', has_r:true}},
            {{id:'mean', zh:'平均数', en:'Mean', aliases:[], search_terms:['平均水平'], topic:'foundations', level:'basic', type:'concept', has_r:false}}
          ];
          const out = {{
            normalized:s.normalizeQuery('  RMSEA　 Test '),
            oral:s.filterTerms('量表结构', {{}}, terms).map(x=>x.id),
            acronym:s.filterTerms('cfa', {{}}, terms).map(x=>x.id),
            rfun:s.filterTerms('lavaan cfa', {{}}, terms).map(x=>x.id),
            combined:s.filterTerms('', {{topic:'factor-analysis',level:'advanced',type:'method',has_r:true}}, terms).map(x=>x.id),
            empty:s.filterTerms('', {{type:'concept'}}, terms).map(x=>x.id),
            zero:s.filterTerms('完全不存在', {{}}, terms).map(x=>x.id)
          }};
          console.log(JSON.stringify(out));
        """)
        self.assertEqual(result["normalized"], "rmsea test")
        for key in ("oral", "acronym", "rfun", "combined"):
            self.assertEqual(result[key], ["cfa"])
        self.assertEqual(result["empty"], ["mean"])
        self.assertEqual(result["zero"], [])

    def test_practice_grades_both_outcomes_and_returns_term_link(self):
        practice_path = json.dumps(str(ASSETS / "practice.js"))
        result = run_node(f"""
          const p = require({practice_path});
          const questions = [{{id:'cfa-1',term_id:'cfa',answer:1,explanation:'解析'}}];
          console.log(JSON.stringify([
            p.gradeQuestion('cfa-1',1,questions),
            p.gradeQuestion('cfa-1',0,questions)
          ]));
        """)
        self.assertTrue(result[0]["correct"])
        self.assertFalse(result[1]["correct"])
        self.assertEqual(result[1]["termLink"], "terms/cfa.html")
        self.assertEqual(result[1]["explanation"], "解析")

    def test_practice_explains_the_selected_option_not_just_the_correct_one(self):
        practice_path = json.dumps(str(ASSETS / "practice.js"))
        result = run_node(f"""
          const p = require({practice_path});
          const questions = [{{id:'q-1',term_id:'q',answer:1,
            options:['甲','乙','丙','丁'],
            option_explanations:['甲错因','乙正确且理由完整','丙错因','丁错因'],
            explanation:'笼统解析'}}];
          console.log(JSON.stringify([0,1,2,3].map(i => p.gradeQuestion('q-1', i, questions))));
        """)
        self.assertEqual([row["explanation"] for row in result], ["甲错因", "乙正确且理由完整", "丙错因", "丁错因"])
        self.assertEqual([row["correct"] for row in result], [False, True, False, False])

    def test_term_quiz_reveals_feedback_for_each_selected_option(self):
        practice_path = json.dumps(str(ASSETS / "practice.js"))
        site_path = json.dumps(str(ASSETS / "site.js"))
        result = run_node(f"""
          const feedback = [{{hidden:true}}, {{hidden:true}}];
          const resultText = {{textContent:''}};
          const choices = [0,1].map(i => ({{
            getAttribute: () => String(i),
            setAttribute: function(k,v) {{ this[k]=v; }},
            classList: {{ add: function(v) {{ this.value=v; }}, remove: function() {{ this.value=''; }} }},
            addEventListener: function(k,fn) {{ this.click=fn; }},
            nextElementSibling: feedback[i]
          }}));
          const quiz = {{
            getAttribute: () => '1',
            querySelectorAll: () => choices,
            querySelector: () => resultText
          }};
          global.document = {{
            querySelectorAll: s => s === '.quiz[data-answer]' ? [quiz] : [],
            getElementById: () => null
          }};
          global.window = global;
          global.PsychPractice = require({practice_path});
          require({site_path});
          choices[0].click();
          const wrong = {{shown:!feedback[0].hidden, status:resultText.textContent}};
          choices[1].click();
          const correct = {{shown:!feedback[1].hidden, oldHidden:feedback[0].hidden, status:resultText.textContent}};
          console.log(JSON.stringify([wrong,correct]));
        """)
        self.assertTrue(result[0]["shown"])
        self.assertIn("错误", result[0]["status"])
        self.assertTrue(result[1]["shown"])
        self.assertTrue(result[1]["oldHidden"])
        self.assertIn("正确", result[1]["status"])

    def test_site_script_has_copy_success_failure_and_tab_wiring(self):
        script = (ASSETS / "site.js").read_text(encoding="utf-8")
        self.assertIn("已复制", script)
        self.assertIn("复制失败", script)
        self.assertIn("data-tab", script)

    def test_build_emits_practice_page(self):
        with tempfile.TemporaryDirectory() as temporary:
            build_site("preview", Path(temporary))
            self.assertTrue((Path(temporary) / "practice.html").exists())

    def test_build_copies_every_shared_interaction_script(self):
        with tempfile.TemporaryDirectory() as temporary:
            build_site("public", Path(temporary))
            shell = (Path(temporary) / "index.html").read_text(encoding="utf-8")
            for script in ("theme.js", "filter-menu.js", "cursor.js", "site.js"):
                self.assertRegex(shell, 'src="assets/' + script.replace('.', r'\.') + r'(?:\?v=[a-f0-9]+)?"')
                self.assertTrue((Path(temporary) / "assets" / script).is_file(), script)

    def test_filter_index_carries_chinese_labels_for_topic_type_and_level(self):
        with tempfile.TemporaryDirectory() as temporary:
            build_site("public", Path(temporary))
            data = json.loads((Path(temporary) / "assets/data/search-index.json").read_text(encoding="utf-8"))
            item = next(row for row in data if row["id"] == "t-test")
            self.assertEqual(item["topic_label"], "差异检验与方差分析")
            self.assertEqual(item["type_label"], "方法")
            self.assertEqual(item["level_label"], "基础")

    def test_local_file_pages_load_embedded_search_and_quiz_data_without_fetch(self):
        with tempfile.TemporaryDirectory() as temporary:
            build_site("public", Path(temporary))
            shell = (Path(temporary) / "practice.html").read_text(encoding="utf-8")
            data_js = Path(temporary) / "assets/data/site-data.js"
            self.assertTrue(data_js.is_file())
            self.assertRegex(shell, r'src="assets/data/site-data\.js(?:\?v=[a-f0-9]+)?"')
            result = run_node(f"""
              global.window = global;
              require({json.dumps(str(data_js))});
              console.log(JSON.stringify({{search:window.PsychSiteData.search.filter(item => item.kind !== 'analysis').length, quizzes:window.PsychSiteData.quizzes.length}}));
            """)
            self.assertEqual(result, {"search": 15, "quizzes": 15})


if __name__ == "__main__":
    unittest.main()
