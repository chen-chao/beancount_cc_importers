import os
import re

from beancount.core.number import ZERO, D
from beangulp.cache import _FileMemo
from beancount.parser.printer import format_entry

from beancount_cc_importers.mssalary import MSSalaryImporter

def test_mssalary():
    importer = MSSalaryImporter([('filename', r".*salary_.*\.json")])
    for test_filename in os.listdir('tests/data'):
        if re.match(r".*salary_.*\.json", test_filename):
            entries = importer.extract(_FileMemo(os.path.join("tests/data", test_filename)))
            assert len(entries) >= 1

            num = ZERO
            for entry in entries:
                for posting in entry.postings:
                    assert isinstance(posting.account, str)
                    assert ':' in posting.account
                    num += posting.units.number
                # print(format_entry(entry))

                assert num <= D(0.001)
