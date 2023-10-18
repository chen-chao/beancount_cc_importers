import csv
import datetime

from beancount.core import data
from beancount.core.number import D
from beancount.ingest.cache import _FileMemo
from beancount.ingest.importers.mixins.identifier import IdentifyMixin
from beancount.ingest.importers.mixins.filing import FilingMixin

class LingQianImporter(IdentifyMixin, FilingMixin):
    '''Beancount importer for Wechat LingQian debts'''
    def __init__(self, account, matchers, encoding='utf-8', currency='CNY', skip_lines=16):
        self.account = account
        self.currency = currency
        self.encoding = encoding
        self.skip_lines = skip_lines

        super().__init__(filing=account, prefix=None, matchers=matchers)

    def extract(self, file: _FileMemo, existing_entries=None):
        entries = []

        with open(file.name, encoding=self.encoding) as f:
            # skip headers
            for i in range(self.skip_lines):
                f.readline()

            reader = csv.DictReader(f)
            for i, row in enumerate(reader, start=self.skip_lines):
                if self._is_lingqian_expense(row) or self._is_lingqian_income(row):
                    try:
                        date = datetime.date.fromisoformat(row['交易时间'].split()[0])
                    except IndexError:
                        raise ValueError(f'date format should be YYYY-MM-DD, current is {row["交易时间"]}')

                    is_expense = row['收/支'] == '支出'
                    amount = D(self._get_number(row['金额(元)']))
                    if is_expense:
                        amount = -amount

                    payee = row['交易对方']
                    narration = row['商品']

                    meta = data.new_metadata(file.name, i)
                    if row['备注'] != '/':
                        meta['note'] = row['备注']

                    postings = [
                        data.Posting(self.account, data.Amount(amount, self.currency), None, None, None, None),
                        data.Posting("_UnknownAccount", data.Amount(-amount, self.currency), None, None, None, None),
                    ]

                    e = data.Transaction(meta, date, flag="*", payee=payee,
                                         narration=narration, tags=data.EMPTY_SET,
                                         links=data.EMPTY_SET, postings=postings)

                    entries.append(e)

        return entries

    def file_date(self, file: _FileMemo):
        # _FileMemo.contents() returns a string
        for i, line in enumerate(file.contents().split('\n')):
            if i == 2:
                try:
                    _, end_time = line.split('终止时间：')

                    # end_time is in format of [2022-12-27 12:51:23]
                    return datetime.date.fromisoformat(end_time[1:11])
                except IndexError:
                    raise ValueError(f'date format should be YYYY-MM-DD, current is {line}')

        raise ValueError(f"malformed format: {file.contents()}, expects 2nd line is the starting and ending time")

    def _get_number(self, s: str) -> str:
        '''¥14.80 -> 14.80'''
        return s[1:]

    def _is_lingqian_expense(self, row: dict) -> bool:
        return row['收/支'] == '支出' and row['支付方式'] == '零钱' and (
            row['当前状态'] == '支付成功' or row['当前状态'] == '已转账' or row['当前状态'] == '对方已收钱')

    def _is_lingqian_income(self, row: dict) -> bool:
        return row['收/支'] == '收入' and (row['当前状态'] == '已存入零钱' or row['当前状态'] == '已收钱')
