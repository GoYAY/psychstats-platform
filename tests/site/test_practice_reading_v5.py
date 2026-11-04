import unittest
from tests.site.test_frontend_assets import run_node
from sitegen.build import _quiz_bank
from sitegen.render import render_practice, page_shell


class PracticeReadingV5Tests(unittest.TestCase):
    def test_detailed_practice_payload_is_loaded_only_by_practice_page(self):
        self.assertIn('assets/data/practice-data.js',render_practice())
        self.assertNotIn('practice-data.js',page_shell('普通页面',''))

    def test_switching_answers_does_not_recount_first_attempt(self):
        result = run_node("""
          const p=require('./site/assets/practice.js');
          if(!p.createSession){console.log(JSON.stringify({missing:true}));process.exit(0)}
          const s=p.createSession([{id:'a',term_id:'a',answer:1,options:['错','对'],option_explanations:['错因','正确理由']},
                                   {id:'b',term_id:'b',answer:0,options:['对','错'],option_explanations:['理由','错因']}]);
          const first=s.choose(0),second=s.choose(1),score=s.score();s.next();
          const unselected=s.selection();s.choose(0);s.next();s.choose(1);
          console.log(JSON.stringify({first:first.correct,second:second.explanation,score,unselected,after:s.score()}));
        """)
        self.assertEqual(result, {'first':False,'second':'正确理由','score':{'correct':0,'answered':1},
                                  'unselected':None,'after':{'correct':1,'answered':2}})

    def test_quiz_reading_contains_real_explanations_and_links_not_another_quiz(self):
        bank = _quiz_bank([{'id':'a','zh':'甲','en':'A','plain_explanation':'看相关系数',
                           'plain_example':'每位学生填问卷','operational_definition':'定义',
                           'sections':[{'heading':'怎么看','body':'观察关系'}],
                           'quiz':{'question':'题目','options':['正确','错误'],'answer':0}},
                          {'id':'r','zh':'相关系数'}])
        reading = bank[0].get('reading_html', '')
        self.assertIn('每位学生填问卷',reading)
        self.assertIn('观察关系',reading)
        self.assertIn('href="terms/r.html"',reading)
        self.assertNotIn('data-choice',reading)


if __name__ == '__main__':
    unittest.main()
