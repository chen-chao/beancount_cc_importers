import csv
import os
import os.path
import tempfile

from beancount.ingest.importers.csv import Importer as CsvImorter
from beancount.ingest.importers.mixins.identifier import IdentifyMixin
from beancount.ingest.importers.mixins.filing import FilingMixin
from beancount.ingest.cache import _FileMemo

from beancount_cc_importers.util.eml2csv import (get_etree_from_eml, EmlToCsvConverter)

class EmlImporter(IdentifyMixin, FilingMixin):
    '''Beancount importer for debt emails from bank CMB/COMM/ABC'''
    def __init__(self, matchers, eml_converter: EmlToCsvConverter, csv_importer: CsvImorter):
        self.account = csv_importer.filing_account
        self.csv_importer = csv_importer
        self.eml_converter = eml_converter
        self.tempfiles = {}

        super().__init__(filing=self.account, prefix=None, matchers=matchers)

    def ensure_csv(self, filename: str):
        if filename in self.tempfiles and os.path.exists(self.tempfiles[filename]):
            return self.tempfiles[filename]

        g_csv = self._gen_csv_path(filename)

        with open(filename, 'r', encoding='utf-8') as eml:
            tree = get_etree_from_eml(eml)

        with open(g_csv, 'w+', encoding='utf-8') as f:
            writer = csv.writer(f)
            self.eml_converter.get_csv(tree, writer)
            # self.eml_converter.get_balance(tree)

        return g_csv

    def extract(self, file, existing_entries=None):
        g_csv = self.ensure_csv(file.name)
        csv_file = _FileMemo(g_csv)
        print(f"g_csv: {g_csv}")
        entries = self.csv_importer.extract(csv_file, existing_entries)

        # remove the tempfile after extracting
        # temp = self.tempfiles.pop(file.name)
        # os.remove(temp)

        return entries

    def file_date(self, file):
        g_csv = self.ensure_csv(file.name)
        csv_file = _FileMemo(g_csv)
        return self.csv_importer.file_date(csv_file)

    def _gen_csv_path(self, filename:str):
        _, temp = tempfile.mkstemp(prefix="beancount-cc-importer-", suffix=".g.csv")
        self.tempfiles[filename] = temp
        return temp