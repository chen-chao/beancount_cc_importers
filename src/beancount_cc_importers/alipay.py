import csv
import datetime

from beancount.core import data
from beancount.core.number import D
from beancount.ingest.cache import _FileMemo
from beancount.ingest.importers.mixins.identifier import IdentifyMixin
from beancount.ingest.importers.mixins.filing import FilingMixin

class YueImporter(IdentifyMixin, FilingMixin):
    '''Beancount importer for Alipay Yu'e debts'''
    def __init__(self, account, matchers, default_payee_account=None, encoding='gb18030', currency='CNY', skip_lines=12):
        self.account = account
        self.currency = currency
        self.encoding = encoding
        self.skip_lines = skip_lines
        if default_payee_account:
            self.default_payee_account = default_payee_account
        else:
            self.default_payee_account = '_UnknownAccount'

        super().__init__(filing=account, prefix=None, matchers=matchers)

    def extract(self, file: _FileMemo, existing_entries=None):
        # row: 流水号,时间,名称,备注,收入,支出,账户余额（元）,资金渠道
        entries = []

        with open(file.name, encoding=self.encoding) as f:
            # skip headers
            for i in range(self.skip_lines):
                f.readline()

            reader = csv.DictReader(f)
            for i, row in enumerate(reader, start=self.skip_lines):
                if self._is_income(row):
                    try:
                        date = datetime.date.fromisoformat(row['时间'].split()[0])
                    except IndexError:
                        raise ValueError(f'date format should be YYYY-MM-DD, current is {row["时间"]}')

                    amount = D(row['收入'])
                    narration = row['名称']
                    meta = data.new_metadata(file.name, i)
                    if row['备注'] != '':
                        meta['note'] = row['备注']

                    postings = [
                        data.Posting(self.account, data.Amount(amount, self.currency), None, None, None, None),
                        data.Posting(self.default_payee_account, data.Amount(-amount, self.currency), None, None, None, None),
                    ]

                    e = data.Transaction(meta, date, flag="*", payee=None,
                                         narration=narration, tags=data.EMPTY_SET,
                                         links=data.EMPTY_SET, postings=postings)

                    entries.append(e)

        return entries

    def file_date(self, file: _FileMemo):
        for i, line in enumerate(file.contents()):
            if i == 6:
                _, end_time = line.split('至')
                # end_time is in format of [2022-12-27 12:51:23]
                try:
                    return datetime.date.fromisoformat(end_time[1:11])
                except IndexError:
                    raise ValueError(f'date format should be YYYY-MM-DD, current is {line}')

        raise ValueError(f"malformed format: {file.contents()}, expects 6th line is the starting and ending time")

    def _is_income(self, row: dict) -> bool:
        return row['收入'] != '' and row['支出'] == ''