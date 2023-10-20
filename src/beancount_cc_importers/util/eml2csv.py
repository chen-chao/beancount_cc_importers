#!/usr/bin/env python3

import abc
import csv
import email
import io
import re
from datetime import date

from lxml import etree

def get_etree_from_eml(eml: io.TextIOWrapper) -> etree._ElementTree:
    msg = email.message_from_file(eml)
    parts = list(msg.walk())
    if len(parts) == 0:
        raise ValueError("invalid email")

    # the last part is often the html
    book = parts[-1]
    payload = book.get_payload(decode=True)
    html = payload.decode(encoding=book.get_content_charset())
    return etree.parse(io.StringIO(html), etree.HTMLParser())

def get_node_text(node: etree._Element) -> str:
    if node is None:
        return ''

    texts = [node.text]
    for e in node.getchildren():
        texts.append(get_node_text(e))

    texts.append(node.tail)

    return ''.join([t.strip() for t in texts if t is not None])

def clean_number(s: str) -> str:
    """1,637.00 -> 1637"""
    if not s:
        return 0
    try:
        return re.match(r'.*?(-?\d+(.\d+)?)', s.replace(',', '')).group(1)
    except AttributeError as err:
        print(f"Cannot clean number: {s}, exception: {err}")
        return 0

def add_missing_year(day_field, start_date, end_date):
    month=int(day_field[:2])
    day=int(day_field[3:5])
    for y in range(start_date.year, end_date.year + 1):
        d = date(year=y, month=month, day=day)
        if d >= start_date and d <= end_date:
            return d
    raise ValueError("no proper day in given period")


class EmlToCsvConverter(metaclass=abc.ABCMeta):
    '''Base class of EML to CSV converter.'''
    @abc.abstractmethod
    def get_csv(self, tree: etree._ElementTree, writer: csv.writer):
        pass

    @abc.abstractmethod
    def get_balance(self, tree: etree._ElementTree) -> str:
        pass


class AbcEmlToCsv(EmlToCsvConverter):
    def get_csv(self, tree: etree._ElementTree, writer: csv.writer):
        headers = ['交易日', '入账日期', '卡号末四位', '交易摘要', '交易地点', '交易金额', '入账金额']
        writer.writerow(headers)

        trs = tree.xpath('//*[contains(@id, "loopBand1")]//*[contains(@id, "fixBand10")]//table//table//tr')
        for tr in trs:
            row = list(map(get_node_text, tr.xpath('.//font')))
            if len(row) < 7:
                # 还款记录
                if len(row) == 6 and row[2] == '':
                    row.insert(4, '')
                else:
                    print(row)
                    continue

            row[-1] = clean_number(row[-1])
            row[-2] = clean_number(row[-2])
            writer.writerow(row)

    def get_balance(self, tree: etree._ElementTree) -> str:
        tr = tree.xpath('//*[contains(@id, "loopBand1")]//*[contains(@id, "fixBand3")]//table//table//tr')[0]
        return clean_number(tr.xpath('.//font')[1])


class CmbEmlToCsv(EmlToCsvConverter):
    def get_csv(self, tree: etree._ElementTree, writer: csv.writer):
        headers = ['交易日', '记账日', '交易摘要', '人民币金额', '卡号末四位', '交易地点', '交易地金额']
        writer.writerow(headers)
        trs = tree.xpath('//*[contains(@id, "fixBand15")]//table//table/tbody/tr')
        start_date, end_date = self._get_period(tree)

        for tr in trs:
            row = list(map(get_node_text, tr.xpath('.//font')))
            # print(row)
            if len(row) < 7:
                continue

            if row[0] == '':
                row[0] = row[1]

            if '/' not in row[1]:
                row[1] = row[1][:2] + '/' + row[1][2:4]

            if '/' not in row[0]:
                row[0] = row[0][:2] + '/' + row[0][2:4]

            row[0] = add_missing_year(row[0], start_date, end_date).isoformat()
            row[1] = add_missing_year(row[1], start_date, end_date).isoformat()

            row[-1] = clean_number(row[-1])
            writer.writerow(row)

    def get_balance(self, tree: etree._ElementTree) -> str:
        tds = tree.xpath('//*[contains(@id, "fixBand40")]//table//table/tbody/tr/td')
        for v in map(get_node_text, tds):
            if v.strip() == '':
                continue
            return clean_number(v)

    def _get_period(self, tree):
        # sample text: 账单周期 2023/01/14-2023/02/13'
        e = tree.xpath("//*[contains(@id, 'statementCycle')]")[0]
        start, end = get_node_text(e).split('-')
        start_date = date.fromisoformat(start.replace('/', '-'))
        end_date = date.fromisoformat(end.replace('/', '-'))
        return start_date, end_date


class CommEmlToCsv(EmlToCsvConverter):
    def get_csv(self, tree: etree._ElementTree, writer: csv.writer):
        repay = tree.xpath('//*[contains(@id, "repayList")]//table')[0]
        headers = map(get_node_text, repay.xpath('.//thead/tr/td'))
        # ,交易日期,记账日期,卡末四位,交易说明,交易金额,入账金额
        writer.writerow(headers)

        start_date, end_date = self._get_period(tree)

        for c in repay.xpath('.//tbody/tr'):
            row = list(map(get_node_text, c.xpath('./td')))
            # date
            row[1] = add_missing_year(row[1], start_date, end_date).isoformat()
            row[2] = add_missing_year(row[2], start_date, end_date).isoformat()

            # 交易金额,入账金额
            row[-1] = '-' + clean_number(row[-1])
            row[-2] = '-' + clean_number(row[-2])
            writer.writerow(row)

        take = tree.xpath('//*[contains(@id, "takeList")]//table')[0]
        for c in take.xpath('.//tbody/tr'):
            row = list(map(get_node_text, c.xpath('./td')))
            # date
            row[1] = add_missing_year(row[1], start_date, end_date).isoformat()
            row[2] = add_missing_year(row[2], start_date, end_date).isoformat()

            # 交易金额,入账金额
            row[-1] = clean_number(row[-1])
            row[-2] = clean_number(row[-2])
            writer.writerow(row)

    def get_balance(self, tree: etree._ElementTree) -> str:
        td = tree.xpath('//*[contains(text(), "本期应还款")]')[0]
        return clean_number(td.getnext().text)

    def _get_period(self, tree: etree._ElementTree):
        # sample text: 账单周期 2023/01/14-2023/02/13
        p = tree.xpath('//*[contains(text(), "账单周期")]')[0]
        fields = p.text.split(' ')
        if len(fields) != 2:
            print(f"Not a valid time period: {p.text}")

        start, end = fields[-1].split('-')
        start_date = date.fromisoformat(start.replace('/', '-'))
        end_date = date.fromisoformat(end.replace('/', '-'))
        return start_date, end_date

class PingAnEmlToCsv(EmlToCsvConverter):
    def get_csv(self, tree: etree._ElementTree, writer: csv.writer):
        tables = tree.xpath("//tr/td/table")
        data = None
        for i, t in enumerate(tables):
            text = t.xpath(".//tr//*[contains(text(), '人民币账户交易明细')]")
            if text:
                try:
                    data = tables[i+1]
                except IndexError:
                    raise ValueError("No data table after 人民币账户交易明细")

                break

        if data is None:
            raise ValueError("人民币账户交易明细 not found")
        
        headers = ['交易日期', '记账日期', '交易说明', '人民币金额']
        writer.writerow(headers)
        for tr in data.xpath(".//tbody/tr"):
            row = list(map(get_node_text, tr.xpath("./td")))
            if len(row) != 4:
                continue

            try:
                # the first field should be date like 2023-09-02
                _ = date.fromisoformat(row[0])
                row[-1] = clean_number(row[-1])
                writer.writerow(row)
            except (ValueError, IndexError):
                # not transaction data, skip to next
                continue

    def get_balance(self, tree: etree._ElementTree) -> str:
        pass