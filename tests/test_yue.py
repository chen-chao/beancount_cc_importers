import os
import re

from beancount.core.number import ZERO, D
from beancount.ingest.cache import _FileMemo
from beancount.parser.printer import format_entry

from beancount_cc_importers.alipay import YueImporter

def test_yue():
    importer = YueImporter('Assets:Alipay:Yuebao', [('filename', r".*ACCLOG.*\.csv")])
    for test_filename in os.listdir('tests/data'):
        if re.match(r".*ACCLOG.*\.csv", test_filename):
            entries = importer.extract(_FileMemo(os.path.join("tests/data", test_filename)))
            assert len(entries) >= 1

            num = ZERO
            for entry in entries:
                for posting in entry.postings:
                    assert isinstance(posting.account, str)
                    # assert ':' in posting.account
                    num += posting.units.number
                print(format_entry(entry))

                assert num <= D(0.001)
