import csv
from dataclasses import dataclass
import datetime

import dateutil.parser
from beancount.core import data
from beancount.core.number import D
from beangulp.importers.mixins.identifier import IdentifyMixin
from beangulp.importers.mixins.filing import FilingMixin
from beangulp.cache import _FileMemo


@dataclass
class CommLoanAccountMap:
    principal: str = "Liabilities:Loan:Estate"
    interest: str = "Expenses:Loan:Interest"
    asset: str = "Asset:Account"


class CommLoanImporter(IdentifyMixin, FilingMixin):
    """Beancount importer for Comm estate debt"""

    def __init__(
        self,
        matchers,
        account_map=None,
        encoding="utf-8",
        currency="CNY",
    ):
        self.encoding = encoding
        self.currency = currency
        self.account_map = (
            account_map
            if account_map is not None
            else CommLoanAccountMap()
        )
        super().__init__(
            filing=self.account_map.asset, prefix=None, matchers=matchers
        )

    def extract(self, file, existing_entries=None):
        entries = []
        last_date = self._get_latest_date(existing_entries)
        with open(file.name, encoding=self.encoding) as f:
            # header:
            # 日期,期数,应还本金,已还本金,已还利息,已还罚息,已还利息复利,已还罚息复利,已还本息合计,本期执行年利率(单利),还款类型,状态
            reader = csv.DictReader(f)
            for i, row in enumerate(reader, start=1):
                date = dateutil.parser.parse(row["日期"]).date()
                if date <= last_date:
                    continue

                principal = D(row["已还本金"])
                interest = (
                    D(row["已还利息"])
                    + D(row["已还罚息"])
                    + D(row["已还利息复利"])
                    + D(row["已还罚息复利"])
                )
                asset = D(row["已还本息合计"])
                meta = data.new_metadata(file.name, i)

                postings = [
                    data.Posting(
                        self.account_map.principal,
                        data.Amount(principal, self.currency),
                        None,
                        None,
                        None,
                        None,
                    ),
                    data.Posting(
                        self.account_map.interest,
                        data.Amount(interest, self.currency),
                        None,
                        None,
                        None,
                        None,
                    ),
                    data.Posting(
                        self.account_map.asset,
                        data.Amount(-asset, self.currency),
                        None,
                        None,
                        None,
                        None,
                    ),
                ]

                e = data.Transaction(
                    meta,
                    date,
                    flag="*",
                    payee="交通银行",
                    narration=f"房贷{row['还款类型']} 第 {row['期数']} 期",
                    tags=data.EMPTY_SET,
                    links=data.EMPTY_SET,
                    postings=postings,
                )

                entries.append(e)
        return entries

    def file_date(self, file):
        with open(file.name, encoding=self.encoding) as f:
            lines = f.readlines()
            if lines:
                return dateutil.parser.parse(lines[-1].split(",")[0]).date()
            return datetime.date.min

    def _get_latest_date(self, existing_entries) -> datetime.date:
        if existing_entries is None:
            return datetime.date.min

        for entry in reversed(existing_entries):
            if isinstance(entry, data.Transaction):
                for posting in entry.postings:
                    if posting.account == self.account_map.principal:
                        return entry.date

        return datetime.date.min
