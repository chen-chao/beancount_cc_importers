#!/usr/bin/env python3

import abc
import csv
import email
import io
import re

from lxml import etree


def get_etree_from_eml(eml: io.TextIOWrapper, encoding: str) -> etree._ElementTree:
    msg = email.message_from_file(eml)
    payload = msg.get_payload(decode=True)
    html = payload.decode(encoding=encoding)
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
    return re.match('.*?(-?\d+(.\d+)?)', s.replace(',', '')).group(1)


class EmlToCsvConverter(metaclass=abc.ABCMeta):
    '''Base class of EML to CSV converter.'''
    @abc.abstractclassmethod
    def get_etree(self, eml: io.TextIOWrapper) -> etree._ElementTree:
        pass

    @abc.abstractmethod
    def get_csv(self, tree: etree._ElementTree, writer: csv.writer):
        pass

    @abc.abstractmethod
    def get_balance(self, tree: etree._ElementTree) -> str:
        pass


class AbcEmlToCsv(EmlToCsvConverter):
    def get_etree(self, eml: io.TextIOWrapper):
        return get_etree_from_eml(eml, encoding='gbk')

    def get_csv(self, tree: etree._ElementTree, writer: csv.writer):
        headers = ['交易日', '入账日期', '卡号末四位', '交易摘要', '交易地点', '交易金额', '入账金额']
        writer.writerow(headers)

        trs = tree.xpath('//*[@id="loopBand1"]//*[@id="fixBand10"]//table//table//tr')
        for tr in trs:
            row = list(map(get_node_text, tr.xpath('.//font')))
            # print(row)
            if len(row) < 7:
                continue

            row[-1] = clean_number(row[-1])
            row[-2] = clean_number(row[-2])
            writer.writerow(row)

    def get_balance(self, tree: etree._ElementTree) -> str:
        tr = tree.xpath('//*[@id="loopBand1"]//*[@id="fixBand3"]//table//table//tr')[0]
        return clean_number(tr.xpath('.//font')[1])


class CmbEmlToCsv(EmlToCsvConverter):
    def get_etree(self, eml: io.TextIOWrapper):
        msg = email.message_from_file(eml)
        cmb = list(msg.walk())[1]
        payload = cmb.get_payload(decode=True)
        html = payload.decode(encoding='utf-8')
        return etree.parse(io.StringIO(html), etree.HTMLParser())

    def get_csv(self, tree: etree._ElementTree, writer: csv.writer):
        headers = ['交易日', '记账日', '交易摘要', '人民币金额', '卡号末四位', '交易地点', '交易地金额']
        writer.writerow(headers)
        trs = tree.xpath('//*[@id="fixBand15"]//table//table/tbody/tr')
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

            row[-1] = clean_number(row[-1])
            writer.writerow(row)

    def get_balance(self, tree: etree._ElementTree) -> str:
        tds = tree.xpath('//*[@id="fixBand40"]//table//table/tbody/tr/td')
        for v in map(get_node_text, tds):
            if v.strip() == '':
                continue
            return clean_number(v)


class CommEmlToCsv(EmlToCsvConverter):
    def get_etree(self, eml: io.TextIOWrapper):
        return get_etree_from_eml(eml, encoding='gbk')

    def get_csv(self, tree: etree._ElementTree, writer: csv.writer):
        repay = tree.xpath('//*[@id="repayList"]//table')[0]
        headers = map(get_node_text, repay.xpath('.//thead/tr/td'))
        # ,交易日期,记账日期,卡末四位,交易说明,交易金额,入账金额
        writer.writerow(headers)

        for c in repay.xpath('.//tbody/tr'):
            row = list(map(get_node_text, c.xpath('./td')))
            # 交易金额,入账金额
            row[-1] = '-' + clean_number(row[-1])
            row[-2] = '-' + clean_number(row[-2])
            writer.writerow(row)

        take = tree.xpath('//*[@id="takeList"]//table')[0]
        for c in take.xpath('.//tbody/tr'):
            row = list(map(get_node_text, c.xpath('./td')))
            # 交易金额,入账金额
            row[-1] = clean_number(row[-1])
            row[-2] = clean_number(row[-2])
            writer.writerow(row)

    def get_balance(self, tree: etree._ElementTree) -> str:
        td = tree.xpath('//*[contains(text(), "本期应还款")]')[0]
        return clean_number(td.getnext().text)
