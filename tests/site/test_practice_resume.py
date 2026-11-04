import unittest
from tests.site.test_frontend_assets import run_node


class PracticeResumeTests(unittest.TestCase):
    def test_return_restores_question_selection_and_first_attempt_score(self):
        result = run_node("""
          const p=require('./site/assets/practice.js');
          const questions=[{id:'a',term_id:'a',answer:1,options:['错','对']},
                           {id:'b',term_id:'b',answer:0,options:['对','错']}];
          const original=p.createSession(questions);
          original.choose(0);original.choose(1);original.next();original.choose(0);
          if(!original.exportState){console.log(JSON.stringify({missing:true}));process.exit(0)}
          const restored=p.createSession(questions,JSON.parse(JSON.stringify(original.exportState())));
          const before={id:restored.current().id,selected:restored.selection(),score:restored.score()};
          restored.choose(1);
          console.log(JSON.stringify({before,after:restored.score(),selected:restored.selection()}));
        """)
        self.assertEqual(result, {'before': {'id': 'b', 'selected': 0, 'score': {'correct': 1, 'answered': 2}},
                                  'after': {'correct': 1, 'answered': 2}, 'selected': 1})

    def test_removed_question_or_invalid_saved_selection_starts_safely(self):
        result = run_node("""
          const p=require('./site/assets/practice.js');
          const questions=[{id:'a',term_id:'a',answer:1,options:['错','对']}];
          const absent=p.createSession(questions,{question_id:'gone',selected:0,first_answers:[['a',1]]});
          const invalid=p.createSession(questions,{question_id:'a',selected:99,first_answers:[['a',99],['missing',0]]});
          console.log(JSON.stringify({absent:{id:absent.current().id,selected:absent.selection(),score:absent.score()},
                                     invalid:{selected:invalid.selection(),score:invalid.score()}}));
        """)
        self.assertEqual(result, {'absent': {'id': 'a', 'selected': None, 'score': {'correct': 0, 'answered': 0}},
                                  'invalid': {'selected': None, 'score': {'correct': 0, 'answered': 0}}})
