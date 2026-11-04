import json
from pathlib import Path
import unittest
from tools.validate_review_examples import validate_practice
from sitegen.render import render_term

ROOT = Path(__file__).resolve().parents[2]


class ResearchWorkflowTests(unittest.TestCase):
    def term(self, slug):
        return json.loads((ROOT/'site/content/drafts'/f'{slug}.json').read_text(encoding='utf-8'))

    def test_pairing_survives_reordering_and_one_sided_missing(self):
        p = dict(self.term('t-test')['r_practice'])
        p['validation_code'] = '''
before <- data.frame(id=c(1,2,3),score=c(10,20,30))
after <- data.frame(id=c(3,1,2),score=c(33,11,22))
aligned <- pair_by_id(before,after)
stopifnot(all(aligned$post-aligned$pre==c(1,2,3)))
after$score[after$id==2] <- NA
aligned <- pair_by_id(before,after)
stopifnot(nrow(aligned)==2,mean(aligned$post-aligned$pre)==2)
'''
        result = validate_practice('pair-fixture',p)
        self.assertTrue(result['verified'],result['stderr'])

    def test_independent_test_direction_matches_report(self):
        p = dict(self.term('t-test')['r_practice'])
        p['validation_code'] = 'stopifnot(unname(independent$estimate[1]-independent$estimate[2])>0,independent$conf.int[1]>0)'
        result = validate_practice('direction-fixture',p)
        self.assertTrue(result['verified'],result['stderr'])

    def test_same_three_group_case_used_for_anova_and_posthoc(self):
        for slug in ['anova','post-hoc-comparison']:
            p = dict(self.term(slug)['r_practice'])
            p['validation_code'] = 'stopifnot(nrow(d)==180,all(table(d$group)==60),all(c("control","retrieval","rereading") %in% levels(d$group)))'
            result = validate_practice(slug,p)
            self.assertTrue(result['verified'],result['stderr'])

    def test_paired_effect_size_uses_difference_sd(self):
        p = dict(self.term('effect-size')['r_practice'])
        p['validation_code'] = 'stopifnot(abs(dz-mean(change)/sd(change))<1e-10,all(is.finite(boot_dz)))'
        result = validate_practice('paired-effect-fixture',p)
        self.assertTrue(result['verified'],result['stderr'])

    def test_five_registered_diagrams_have_files_and_descriptions(self):
        diagrams = json.loads((ROOT/'site/content/diagram_samples.json').read_text(encoding='utf-8'))
        for slug in ['t-test','anova','standard-error','number-of-factors','measurement-invariance']:
            self.assertIn(slug,diagrams)
            entry = diagrams[slug]
            self.assertTrue(entry['alt'])
            self.assertTrue(entry['caption'])
            for key in ['file','mobile_file']:
                self.assertTrue((ROOT/'site/assets/diagrams'/entry[key]).is_file())

    def test_core_analysis_pages_have_specific_report_and_limits(self):
        for slug in ['t-test','anova','post-hoc-comparison','correlation-coefficient','effect-size','statistical-power','efa','cfa','logistic-regression','multiple-regression','moderation-effect','simple-slope-test']:
            term = self.term(slug)
            html = render_term(term,preview=True)
            self.assertIn('研究结果怎么写',html)
            self.assertIn('使用与解释时的检查',html)
            self.assertLess(html.index('使用与解释时的检查'),html.index('研究结果怎么写'))
            self.assertTrue(term['r_practice'].get('report_example'))
