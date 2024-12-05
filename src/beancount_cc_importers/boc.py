import datetime
import re

from beancount.core import data
from beancount.core.number import D
from beangulp.importers.mixins.identifier import IdentifyMixin
from beangulp.importers.mixins.filing import FilingMixin

from beancount_cc_importers.util.azure_recognizer import AzureDocumentRecognizer


class BocTransaction:
    account: str
    filename: str
    row: int

    # keys:  ["交易日", "银行记账日", "卡号后四位", "交易描述", "存入", "支出"]
    column_map: dict
    records: dict

    def __init__(self, account: str, filename: str, row: int, column_map: dict):
        self.account = account
        self.filename = filename
        self.row = row
        self.column_map = column_map
        self.records = {}

    def read_cell(self, index: int, content: str):
        if index in self.column_map:
            self.records[self.column_map[index]] = content

    def create_beancount_transaction(self) -> data.Transaction:
        if len(self.records) < len(self.column_map):
            missing_keys = set(self.column_map.values()) - set(
                self.records.keys()
            )
            raise ValueError(f"Keys are missing: {missing_keys}")

        meta = data.new_metadata(self.filename, self.row)
        meta["card"] = self.records["卡号后四位"]
        meta["date"] = self.records["银行记账日"]
        currency = "CNY"
        if self.records["存入"].strip() != "":
            amount = self.records["存入"]
        else:
            amount = "-" + self.records["支出"].strip()

        number = D(amount)
        postings = [
            data.Posting(
                self.account,
                data.Amount(number, currency),
                None,
                None,
                None,
                None,
            ),
            data.Posting(
                "_UnknownAccount",
                data.Amount(-number, currency),
                None,
                None,
                None,
                None,
            ),
        ]

        e = data.Transaction(
            meta,
            datetime.date.fromisoformat(self.records["交易日"]),
            flag="*",
            payee=self.records["交易描述"],
            narration="/",
            tags=data.EMPTY_SET,
            links=data.EMPTY_SET,
            postings=postings,
        )
        return e


class BocPdfImporter(IdentifyMixin, FilingMixin):
    def __init__(self, account: str, matchers, form_recognizer=None):
        self.account = account

        if form_recognizer is None:
            form_recognizer = AzureDocumentRecognizer()
        self.form_recognizer = form_recognizer

        super().__init__(filing=account, prefix=None, matchers=matchers)

    def extract(self, file, existing_entries=None):
        transactions = None
        tables = self.form_recognizer.analyze(file.name).tables
        for table in tables:
            if len(table.cells) > 0 and table.cells[0].content.startswith(
                "交易日"
            ):
                transactions = table
                break
        if transactions is None:
            return []

        entries = []
        columns = set(
            ["交易日", "银行记账日", "卡号后四位", "交易描述", "存入", "支出"]
        )
        column_map = {}
        row_index = 0
        cell_index = 0
        while cell_index < len(transactions.cells):
            cell = transactions.cells[cell_index]
            if cell.row_index != 0:
                break
            for column in columns:
                if transactions.cells[cell_index].content.startswith(column):
                    column_map[transactions.cells[cell_index].column_index] = (
                        column
                    )
                    columns.remove(column)
                    break
            cell_index += 1

        if len(columns) != 0:
            raise ValueError(f"Row 0 is missing columns {columns}")

        row_index += 1
        while cell_index < len(transactions.cells):
            # processing a row
            row_data = BocTransaction(
                self.account, file.name, row_index, column_map
            )
            while (
                cell_index < len(transactions.cells)
                and transactions.cells[cell_index].row_index == row_index
            ):
                cell = transactions.cells[cell_index]
                row_data.read_cell(cell.column_index, cell.content)

                cell_index += 1

            if cell_index < len(transactions.cells):
                assert transactions.cells[cell_index].row_index == row_index + 1

            entries.append(row_data.create_beancount_transaction())
            row_index += 1

        return entries

    def file_date(self, file):
        match = re.match(r"(.*(\d{4})年(\d{1,2})月", file.name)
        if match:
            year = int(match.group(1))
            month = int(match.group(2))
            return datetime.date(year, month, 1)
        else:
            return datetime.date.today()
