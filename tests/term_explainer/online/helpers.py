from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

def environment(root):
    return {
        'TERM_PRIVATE_ROOT':str(Path(root)/'private'),
        'TERM_PUBLIC_ROOT':str(Path(root)/'public'),
        'TERM_ORIGIN':'https://cdst.site',
        'TERM_API_PREFIX':'/psy-stats-test/api/term-explainer/',
        'TERM_MAX_JOB_CALLS':'80', 'TERM_MAX_DAILY_CALLS':'200',
        'TERM_MAX_JOB_TOKENS':'1000000', 'TERM_MAX_DAILY_TOKENS':'2000000',
        'TERM_MAX_OUTPUT_TOKENS':'8192', 'TERM_MAX_JOB_NETWORK_CALLS':'20',
        'TERM_MAX_DAILY_NETWORK_CALLS':'40', 'TERM_MAX_FILE_BYTES':'20000000',
        'TERM_MAX_TOTAL_BYTES':'40000000', 'TERM_MAX_FILES':'3',
        'TERM_MAX_PAGES':'150', 'TERM_MAX_TEXT_CHARS':'500000',
        'TERM_MAX_TASK_SECONDS':'7200', 'TERM_MAX_QUEUE':'10',
        'TERM_REQUEST_TIMEOUT':'90',
    }

class OnlineCase(unittest.TestCase):
    def setUp(self):
        self.temp=TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.env=environment(self.root)
