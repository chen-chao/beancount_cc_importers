import csv
import os
import os.path

from beancount.ingest.importers.csv import Importer as CsvImorter
from beancount.ingest.importers.mixins.identifier import IdentifyMixin
from beancount.ingest.importers.mixins.filing import FilingMixin
from beancount.ingest.cache import _FileMemo

from beancount_cc_importers.util.eml2csv import EmlToCsvConverter

class EmlImporter(IdentifyMixin, FilingMixin):
    '''Beancount importer for debt emails from bank CMB/COMM/ABC'''
    def __init__(self, matchers, eml_converter: EmlToCsvConverter, csv_importer: CsvImorter):
        self.account = csv_importer.filing_account
        self.csv_importer = csv_importer
        self.eml_converter = eml_converter

        super().__init__(filing=self.account, prefix=None, matchers=matchers)

    def ensure_csv(self, filename: str):
        g_csv = self._gen_csv_path(filename)

        if not os.path.exists(g_csv):
            with open(filename, 'r', encoding='utf-8') as eml:
                tree = self.eml_converter.get_etree(eml)

            with open(g_csv, 'w+', encoding='utf-8') as f:
                writer = csv.writer(f)
                self.eml_converter.get_csv(tree, writer)
                # self.eml_converter.get_balance(tree)

        return g_csv

    def extract(self, file, existing_entries=None):
        g_csv = self.ensure_csv(file.name)
        csv_file = _FileMemo(g_csv)
        return self.csv_importer.extract(csv_file, existing_entries)

    def file_date(self, file):
        g_csv = self.ensure_csv(file.name)
        csv_file = _FileMemo(g_csv)
        return self.csv_importer.file_date(csv_file)

    def _gen_csv_path(self, filename:str):
        current_dir = os.path.dirname(__file__)
        g_dir = os.path.join(os.path.dirname(current_dir), 'gen')
        if not os.path.exists(g_dir):
            os.mkdir(g_dir)

        basename = os.path.basename(filename)
        barename, _ = os.path.splitext(basename)
        g_csv = barename + '.g.csv'

        full_csv = os.path.join(g_dir, g_csv)
        return full_csv
