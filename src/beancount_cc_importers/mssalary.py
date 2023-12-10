import datetime
import json
from dataclasses import dataclass
from decimal import Decimal

from beancount.core import data
from beancount.core.number import D, ZERO
from beancount.ingest.importers.mixins.identifier import IdentifyMixin
from beancount.ingest.importers.mixins.filing import FilingMixin


@dataclass
class MSSalaryAccountMap:
    base_salary: str = "Income:BasicPay"
    sactuary_deduction: str = "Income:StatutoryDeduction"

    benefit: str = "Income:Benefit"
    annual_bonus: str = "Income:AnnualBonus"
    bank: str = "Assets:Cash:Cmb"
    stock_selling_income: str = "Equity:WithHeld:StockSale"
    stock_refund: str = "Equity:WithHeld:Stock"
    meal_allowance: str = "Income:MealAllowance"
    espp_selling_income: str = "Equity:WithHeld:EsppDividend"

    espp: str = "Equity:WithHeld:EsppInvest"

    pension: str = "Expenses:Insurance:Pension"
    medical: str = "Expenses:Insurance:Medical"
    unemployment: str = "Expenses:Insurance:Unemployment"
    maternaty: str = "Expenses:Insurance:Maternaty"
    work_injury: str = "Expenses:Insurance:WorkInjury"

    housefund: str = "Assets:Housefund"

    income_tax: str = "Expenses:Tax:Salary"
    annualbonus_tax: str = "Expenses:Tax:Reward"


class MSSalaryImporter(IdentifyMixin, FilingMixin):
    def __init__(
        self,
        matchers,
        account_map=None,
        description="MS salary",
        currency="CNY",
        precision=2,
    ):
        if account_map is None:
            account_map = MSSalaryAccountMap()

        self.account_map = account_map
        self.description = description
        self.currency = currency
        self.precision = precision

        super().__init__(filing=account_map.base_salary, prefix=None, matchers=matchers)

    def extract(self, file, existing_entries=None):
        with open(file.name, "r", encoding="utf-8") as f:
            d: dict = json.load(f)

        assert "payments" in d

        latest_date = self._get_latest_date(existing_entries)

        entries = []
        for payment in reversed(d["payments"]):
            assert "date" in payment
            assert "id" in payment
            assert "buckets" in payment
            assert "amount" in payment

            curdate = datetime.date.fromisoformat(payment["date"])
            if curdate <= latest_date:
                continue

            if len(payment["buckets"]) == 0:
                continue

            e = self._get_transaction(file.name, payment)
            entries.append(e)

        return entries

    def file_date(self, file):
        with open(file.name, "r", encoding="utf-8") as f:
            d = json.load(f)

        return self._get_date(d["payments"][-1]["date"])

    def _get_transaction(self, filename: str, record: dict) -> data.Transaction:
        meta = data.new_metadata(filename, 1)  # TODO: set real lino
        meta["category"] = "china-income-tax"
        date = self._get_date(record["date"])
        postings = []
        entry = data.Transaction(
            meta,
            date,
            flag="*",
            payee=None,
            narration=self.description,
            tags=data.EMPTY_SET,
            links=data.EMPTY_SET,
            postings=postings,
        )

        if record["buckets"]:
            for bucket in record["buckets"]:
                if bucket["id"] == "B10":  # ESPP Contribution
                    entry = self._handle_espp(entry, bucket)
                elif bucket["id"] == "B15":  # insurance
                    entry = self._handle_insurance(entry, bucket)
                elif bucket["id"] == "B25":  # bank transfer
                    entry = self._handle_bank_transfer(entry, bucket)
                elif bucket["id"] == "B05":  # income tax deduction
                    entry = self._handle_tax_deduction(entry, bucket)
                elif bucket["id"] == "B16":  # sactuary deduction
                    entry = self._handle_sactuary_deduction(entry, bucket)
                elif bucket["id"] == "B01":  # salary income
                    entry = self._handle_salary(entry, bucket)
                else:
                    raise ValueError(
                        f"Unknown bucket, id: {bucket['id']}, label: {bucket['label']}"
                    )

        return entry

    def _get_date(self, date: str):
        """Get a |datetime.date| object from date string like 2022-12-07."""
        return datetime.date.fromisoformat(date)

    def _get_latest_date(self, existing_entries) -> datetime.date:
        if existing_entries is None:
            return datetime.date.min

        for entry in reversed(existing_entries):
            if isinstance(entry, data.Transaction):
                for posting in entry.postings:
                    if posting.account == self.account_map.base_salary:
                        return entry.date

        return datetime.date.min

    def _handle_espp(self, entry, bucket) -> data.Transaction:
        assert len(bucket["wagetypes"]) == 1
        p = data.Posting(
            self.account_map.espp,
            data.Amount(
                self._format_amount(bucket["wagetypes"][0]["amount"]), self.currency
            ),
            None,
            None,
            None,
            None,
        )
        entry.postings.append(p)
        return entry

    def _handle_insurance(self, entry, bucket) -> data.Transaction:
        for w in bucket["wagetypes"]:
            if w["amount"] == 0:
                continue

            if w["id"] == "/313Pension":
                account = self.account_map.pension
            elif w["id"] == "/362Public Housing Fund":
                account = self.account_map.housefund
            elif w["id"] == "/403Tax from Salary":
                account = f"{self.account_map.income_tax}:{entry.date.year}"
            elif w["id"] == "/404Tax from Bonus":
                account = self.account_map.annualbonus_tax
            else:
                account = w["id"].replace(" ", "_")

            p = data.Posting(
                account,
                data.Amount(self._format_amount(w["amount"]), self.currency),
                None,
                None,
                None,
                None,
            )
            entry.postings.append(p)

        return entry

    def _handle_bank_transfer(self, entry, bucket) -> data.Transaction:
        assert len(bucket["wagetypes"]) == 1
        p = data.Posting(
            self.account_map.bank,
            data.Amount(
                self._format_amount(bucket["wagetypes"][0]["amount"]), self.currency
            ),
            None,
            None,
            None,
            None,
        )
        entry.postings.append(p)
        return entry

    def _handle_tax_deduction(self, entry, bucket) -> data.Transaction:
        entry.meta["tax-deduction"] = self._format_amount(bucket["amount"])
        return entry

    def _handle_salary(self, entry: data.Transaction, bucket: dict) -> data.Transaction:
        for w in bucket["wagetypes"]:
            if w["amount"] == 0:
                continue

            if w["id"] == "1101Basic Pay":
                account = self.account_map.base_salary
            elif w["id"] == "3236Vested Stock Tax Refund":
                account = self.account_map.stock_refund
            elif w["id"] == "3254MS Meal Allowance":
                account = self.account_map.meal_allowance
            elif w["id"] == "3316ESPP Selling Income":
                account = self.account_map.espp_selling_income
            elif w["id"] == "3032Annual Bonus - CBI":
                account = self.account_map.annual_bonus
            elif w["id"] == "3238Stock Related Payment":
                account = self.account_map.stock_selling_income
            elif w["id"] == "3214Festival Allowance":
                account = self.account_map.benefit
            else:
                account = w["id"].replace(" ", "_")

            p = data.Posting(
                account,
                -data.Amount(self._format_amount(w["amount"]), self.currency),
                None,
                None,
                None,
                None,
            )
            entry.postings.append(p)

        return entry

    def _handle_sactuary_deduction(
        self, entry: data.Transaction, bucket: dict
    ) -> data.Transaction:
        total = ZERO

        for w in bucket["wagetypes"]:
            if w["amount"] == 0:
                continue

            if w["id"] == "/363Public Housing Fund":
                account = self.account_map.housefund
            elif w["id"] == "/314Pension":
                account = self.account_map.pension
            elif w["id"] == "/324Unemployment":
                account = self.account_map.unemployment
            elif w["id"] == "/334Medical":
                account = self.account_map.medical
            elif w["id"] == "/344Work Related Injury":
                account = self.account_map.work_injury
            elif w["id"] == "/354Maternity":
                account = self.account_map.maternaty
            else:
                account = w["id"].replace(" ", "_")

            amount = self._format_amount(w["amount"])
            total += amount
            p = data.Posting(
                account,
                data.Amount(amount, self.currency),
                None,
                None,
                None,
                None,
            )
            entry.postings.append(p)

        entry.postings.append(
            data.Posting(
                self.account_map.sactuary_deduction,
                data.Amount(-total, self.currency),
                None,
                None,
                None,
                None,
            )
        )

        return entry

    def _format_amount(self, amount: float) -> Decimal:
        v = f"{{:.{self.precision}f}}".format(amount)
        return D(v)
