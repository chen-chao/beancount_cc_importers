import os
import re

from beancount.core.number import ZERO, D
from beancount.ingest.cache import _FileMemo
from beancount.parser.printer import format_entry

from beancount_cc_importers.comm_loan import CommLoanImporter

def test_mssalary():
    importer = CommLoanImporter([('filename', r"交通银行房贷还款表.*\.csv")])
    for test_filename in os.listdir('tests/data'):
        if re.match(r"交通银行房贷还款表.*\.csv", test_filename):
            entries = importer.extract(_FileMemo(os.path.join("tests/data", test_filename)))
            assert len(entries) >= 1

            num = ZERO
            for entry in entries:
                for posting in entry.postings:
                    assert isinstance(posting.account, str)
                    assert ':' in posting.account
                    num += posting.units.number

                assert num <= D(0.001)