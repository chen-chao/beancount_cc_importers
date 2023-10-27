import os
import re
import io
import csv

from beancount_cc_importers.util.eml2csv import (
    get_etree_from_eml, EmlToCsvConverter,
     CommEmlToCsv, AbcEmlToCsv, CmbEmlToCsv, PingAnEmlToCsv)

# filter all files started with "交通银行" in tests/data folder

class EmlConverterRunner:
    def __init__(self, converter: EmlToCsvConverter, filename_pattern: str) -> None:
        self.converter = converter
        self.filename_pattern = filename_pattern

    def run(self, test_filename: str):
        if re.match(self.filename_pattern, test_filename):
            s = io.StringIO()
            writer = csv.writer(s)
            with open(test_filename, 'r', encoding='utf-8') as f:
                tree = get_etree_from_eml(f)
                self.converter.get_csv(tree, writer)
                lines = s.getvalue().strip().split('\n')
                assert len(lines) > 1
   
def test_emlConverters():
    converters = [
        EmlConverterRunner(CommEmlToCsv(), r'.*交通银行.*\.eml'),
        EmlConverterRunner(AbcEmlToCsv(), r'.*中国农业银行.*\.eml'),
        EmlConverterRunner(CmbEmlToCsv(), r'.*招商银行.*\.eml'),
        EmlConverterRunner(PingAnEmlToCsv(), r'.*平安.*\.eml'),
    ]

    for test_filename in os.listdir('tests/data'):
        for converter in converters:
            converter.run(os.path.join('tests/data', test_filename))