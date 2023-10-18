import datetime
import json

from beancount.core import data
from beancount.core.number import D
from beancount.ingest.importers.mixins.identifier import IdentifyMixin
from beancount.ingest.importers.mixins.filing import FilingMixin


class CmbJsonImporter(IdentifyMixin, FilingMixin): 
    def __init__(self, account: str, matchers):
        self.account = account
        super().__init__(filing=account, prefix=None, matchers=matchers) 

    def extract(self, file, existing_entries=None):
        with open(file.name, 'r', encoding='utf-8') as f:
            d = json.load(f)

        entries = []
        for record in d["data"]["detail"]:
            e = self._get_transaction(file.name, record)
            entries.append(e)

        return entries

    def file_date(self, file):
        with open(file.name, 'r', encoding='utf-8') as f:
            d = json.load(f)

        return self._get_date(d['data']['rmbBillInfo']['billCycleEnd'])

    def _get_transaction(self, filename: str, record: dict) -> data.Transaction:
        meta = data.new_metadata(filename, int(record["billId"]))

        date = self._get_date(record['billDate'])
        meta["card"] = record["cardNo"]
        meta["date"] = date.isoformat()
        
        description = record["description"]

        currency = "CNY"
        number = -D(record["amount"])
        postings = [
            data.Posting(self.account, data.Amount(number, currency), None, None, None, None),
            data.Posting("_UnknownAccount", data.Amount(-number, currency), None, None, None, None),
        ]

        e = data.Transaction(meta, date, flag="*", payee=None,
                            narration=description, tags=data.EMPTY_SET,
                            links=data.EMPTY_SET, postings=postings)
        return e

    def _get_date(self, date: str):
        '''Get a |datetime.date| object from date string like 20221207.'''
        return datetime.date(int(date[:4]), int(date[4:6]), int(date[6:8]))