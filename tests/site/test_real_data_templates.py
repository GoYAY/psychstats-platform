import json
from pathlib import Path
import unittest

from tools.validate_review_examples import validate_practice

ROOT = Path(__file__).resolve().parents[2]


class RealDataTemplateTests(unittest.TestCase):
    def practice(self, slug):
        return json.loads((ROOT/'site/content/drafts'/f'{slug}.json').read_text(encoding='utf-8'))['r_practice']

    def run_template(self, slug, fixture, assertions):
        p = dict(self.practice(slug))
        p['example_code'] = fixture + '\n' + p['your_data_code']
        p['validation_code'] = assertions
        result = validate_practice(slug+'-user-fixture', p)
        self.assertTrue(result['verified'], result['stderr'])

    def test_cleaning_without_duplicate_rows(self):
        self.run_template('data-cleaning', '''
fixture <- data.frame(id=1:4,gender=c("female","male","female","male"),
 age_text=c("20","21","22","23"),stress=c(30,40,50,60))
write.csv(fixture,"your_data.csv",row.names=FALSE)
''', 'stopifnot(nrow(clean)==4,nrow(log)==0)')

    def test_reverse_scoring_without_invalid_rows(self):
        self.run_template('reverse-scoring', '''
fixture <- data.frame(id=101:106,q2=c(1,2,3,4,5,NA))
write.csv(fixture,"your_data.csv",row.names=FALSE)
''', 'stopifnot(identical(clean$id,101:106),nrow(log)==0,all(clean$q2_reverse[1:5]==5:1))')

    def test_scale_scoring_consumes_user_rows(self):
        self.run_template('scale-scoring', '''
fixture <- data.frame(id=101:106,q1=1,q2=5,q3=1,q4=1)
write.csv(fixture,"your_data.csv",row.names=FALSE)
''', 'stopifnot(nrow(raw)==6,identical(raw$id,101:106),all(score==1))')

    def test_cross_validation_does_not_inject_missingness(self):
        self.run_template('cross-validation', '''
set.seed(77)
fixture <- data.frame(well_being=rnorm(40),stress=rnorm(40),social_support=rnorm(40),age=rnorm(40))
write.csv(fixture,"your_data.csv",row.names=FALSE)
''', 'stopifnot(nrow(d)==40,!anyNA(d$stress),all(is.finite(pred)))')

    def test_comparison_templates_consume_user_data(self):
        fixture = '''
set.seed(77)
fixture <- data.frame(group=rep(c("control","retrieval","rereading"),each=8),gain=rnorm(24))
write.csv(fixture,"your_data.csv",row.names=FALSE)
'''
        for slug in ['welch-anova','planned-contrast','equivalence-testing']:
            with self.subTest(slug=slug):
                self.run_template(slug, fixture, 'stopifnot(nrow(d)==24,abs(mean(d$gain)-mean(fixture$gain))<1e-12)')

    def test_fisher_template_uses_observed_counts(self):
        self.run_template('fisher-exact-test', '''
fixture <- data.frame(group=rep(c("A","B"),each=20),response=rep(c("event","no_event"),20))
write.csv(fixture,"your_data.csv",row.names=FALSE)
''', 'stopifnot(sum(tab)==40,all(tab==10))')

    def test_logistic_overflow_cannot_be_verified(self):
        p = dict(self.practice('logistic-regression'))
        p['example_code'] = p['example_code'].replace(
            'd <- read.csv("binary_outcome_teaching.csv")',
            'd <- read.csv("binary_outcome_teaching.csv")\nd$stress <- d$stress/10000'
        ).replace('stress=c(35,55)', 'stress=c(35,55)/10000')
        result = validate_practice('logistic-unit-overflow', p)
        self.assertFalse(result['verified'], result['stdout'])

    def test_invariance_checks_second_group_residuals(self):
        p = dict(self.practice('measurement-invariance'))
        p['validation_code'] = '''
second_theta <- which(names(scalar@Model@GLIST)=="theta")[2]
scalar@Model@GLIST[[second_theta]][1,1] <- -1
rejected <- tryCatch({assert_measurement_fit(scalar);FALSE},error=function(e)TRUE)
stopifnot(exists("assert_measurement_fit"),rejected)
'''
        result = validate_practice('second-group-residual-fixture', p)
        self.assertTrue(result['verified'], result['stderr'])

    def test_cleaning_and_scoring_logs_multiple_events(self):
        self.run_template('data-cleaning', '''
fixture <- data.frame(id=c(1,1,2,2),gender="female",age_text="20",stress=30)
write.csv(fixture,"your_data.csv",row.names=FALSE)
''', 'stopifnot(nrow(clean)==2,nrow(log)==2)')
        self.run_template('reverse-scoring', '''
fixture <- data.frame(id=101:104,q2=c(0,9,3,NA))
write.csv(fixture,"your_data.csv",row.names=FALSE)
''', 'stopifnot(nrow(clean)==4,nrow(log)==2,all(log$id==101:102))')
