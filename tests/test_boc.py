import os
import re
import json

from beancount.core.number import ZERO, D
from beancount.ingest.cache import _FileMemo
from beancount.parser.printer import format_entry

from beancount_cc_importers.boc import BocPdfImporter


class DictAccesor:
    def __init__(self, properties: dict):
        self.properties = properties

    def __getattr__(self, name):
        # transform snake_case to camelCase
        camel_case = []
        for i in range(len(name)):
            if name[i] == "_":
                continue
            if i > 0 and name[i - 1] == "_":
                camel_case.append(name[i].upper())
            else:
                camel_case.append(name[i].lower())

        name = "".join(camel_case)
        prop = self.properties.get(name)

        if prop is None:
            raise AttributeError(name)

        if isinstance(prop, dict):
            return DictAccesor(prop)

        if isinstance(prop, list):
            return [DictAccesor(p) if isinstance(p, dict) else p for p in prop]

        return prop


class FakeAzureFormRecognizer:
    def __init__(self, result_file):
        with open(result_file, "r", encoding="utf-8") as f:
            self.result = DictAccesor(json.load(f))

    def analyze(self, file_name: str):
        return self.result.analyze_result.tables


def test_yue():
    if not os.path.exists("tests/data/azure_document_results.json"):
        return

    importer = BocPdfImporter(
        "Liabilities:Boc",
        [("filename", r".*中国银行信用卡电子合并账单.*\.PDF")],
        form_recognizer=FakeAzureFormRecognizer(
            "tests/data/azure_document_results.json"
        ),
    )

    for test_filename in os.listdir("tests/data"):
        if re.match(r".*中国银行信用卡电子合并账单.*\.PDF", test_filename):
            entries = importer.extract(
                _FileMemo(os.path.join("tests/data", test_filename))
            )
            assert len(entries) >= 1

            num = ZERO
            for entry in entries:
                for posting in entry.postings:
                    assert isinstance(posting.account, str)
                    # assert ':' in posting.account
                    num += posting.units.number
                # print(format_entry(entry))

                assert num <= D(0.001)


test_yue()
