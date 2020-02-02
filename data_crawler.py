import requests
from bs4 import BeautifulSoup
import csv
import re
import pandas as pd

DOMAIN = "https://markets.businessinsider.com"
header = {"accept": "*/*",
          "accept-encoding": "gzip, deflate, br",
          "content-length": "0",
          "origin": "https://markets.businessinsider.com",
          "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/79.0.3945.117 Safari/537.36",
          "sec-fetch-mode": "cors",
          "sec-fetch-site": "same-origin",
          "x-requested-with": "XMLHttpRequest"}
browser_header = {
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/79.0.3945.117 Safari/537.36"}
INFO_LIST = ['ISIN', 'Issue Date', 'Coupon', 'Maturity Date']


class DataCrawler:
    def __init__(self, url):
        self.url = url
        self.header = header
        self.soup = BeautifulSoup(requests.get(self.url, headers=browser_header).content, 'lxml')

    def ajax_token_finder(self):
        lst = self.soup.find_all('input')
        str_lst = list(map(str, lst))
        attr = []
        result = {}

        for val in str_lst:
            if "ajax" in val:
                attr.append(val)

        for val in attr:
            if "__atts" in val:
                index = val.find("value=")
                index += 7
                atts = ""
                while val[index] != "\"":
                    atts += val[index]
                    index += 1
                result["__atts"] = atts
            elif "__ath" in val:
                index = val.find("value=")
                index += 7  # len("value=\"")
                ath = ""
                while val[index] != "\"":
                    ath += val[index]
                    index += 1
                result["__ath"] = ath
            elif "__atcrv" in val:
                index = val.find("value=")
                index += 7  # len("value=\"")
                atcrv = ""
                while val[index] != "\"":
                    atcrv += val[index]
                    index += 1
                result["__atcrv"] = str(eval(atcrv))
            else:
                raise FileNotFoundError("No __atts, __ath and __atcrv in the string")
        result["referer"] = self.url
        self.update_header(result)

    def update_header(self, new_header):
        self.header.update(new_header)

    def get_instrument_url(self):
        lst = self.soup.find_all('input')
        str_lst = list(map(str, lst))
        result = ""
        for val in str_lst:
            if "instrumentUrl" in val:
                index = val.find("value=")
                index += 7
                value = ""
                while val[index] != "\"":
                    value += val[index]
                    index += 1
                result = value.split("%2f")[-2]

        if len(result) == 0:
            raise FileNotFoundError("Not found instrumentUrl")

        return result

    @staticmethod
    def get_requested_stock_market():
        """
        market_name can be ["Berlin", "Düsseldorf", "Frankfurt", "München", "Stuttgart"]
        Note: u and ü are equivalent. For example, key "Düsseldorf" and "Dusseldorf" will get the same output.

        """
        # result = {"Berlin": "BER", "Düsseldorf": "DUS", "Frankfurt": "FSE", "München": "MUN", "Stuttgart": "STU",
        #           "Dusseldorf": "DUS", "Munchen": "MUN"}
        # market_name = input("Please enter a market name (it can be Berlin, Düsseldorf (Dusseldorf if you can't type ü), Frankfurt, München (Munchen if you can't type ü), Stuttgart):  ")
        # while market_name not in result:
        #     market_name = input(
        #         "Name not in the provided list (it can be Berlin, Düsseldorf (Dusseldorf if you can't type ü), Frankfurt, München (Munchen if you can't type ü), Stuttgart):  ")
        # return result[market_name]
        return "FSE"

    @staticmethod
    def get_start_date():
        # start_date = input("Please enter start date (in the form of dd-mm-yyyy): ")
        # regex = re.compile("(0[1-9]|[12][0-9]|3[01])[-](0[1-9]|1[012])[-](19|20)\d\d")
        # while regex.match(start_date) is None:
        #     start_date = input("Please enter start date ***(IN THE FORM OF dd-mm-yyyy)***: ")
        # return start_date
        return "02-01-2020"

    @staticmethod
    def get_end_date():
        # end_date = input("Please enter end date (in the form of dd-mm-yyyy): ")
        # regex = re.compile("(0[1-9]|[12][0-9]|3[01])[-](0[1-9]|1[012])[-](19|20)\d\d")
        # while regex.match(end_date) is None:
        #     end_date = input("Please enter start date ***(IN THE FORM OF dd-mm-yyyy)***: ")
        # return end_date
        return "15-01-2020"

    def url_generator(self):
        instrument_url = self.get_instrument_url()
        start_date = DataCrawler.get_start_date()
        end_date = DataCrawler.get_end_date()
        requested_stock_market = self.get_requested_stock_market()
        url_generate = DOMAIN + "/Ajax/BondController_HistoricPriceList/" + instrument_url + "/" \
                       + requested_stock_market + "/" + start_date + "_" + end_date
        return url_generate

    def get_content(self, data_url):
        s = requests.Session()
        s.headers.update(self.header)
        if s.post(data_url).status_code != 200:
            print(self.url)
            raise NoAuthorizationError()
        return s.post(data_url).content

    @staticmethod
    def get_bond_info(text):
        bs = BeautifulSoup(text, 'lxml')
        df = pd.DataFrame(index=range(0, 4), columns=['info', 'content'])
        row_marker = 0
        table = bs.find_all("table")[3]

        for row in table.find_all("tr"):
            column_marker = 0
            columns = row.find_all("td")
            column_number = len(columns)
            if column_number <= 1:
                continue
            if columns[0].get_text().strip() in INFO_LIST:
                for column in columns:
                    df.iat[row_marker, column_marker] = column.get_text().strip()
                    column_marker += 1
                row_marker += 1
            else:
                continue
        for col in df:
            try:
                df[col] = df[col].astype(float)
            except ValueError:
                pass
            return df

    @staticmethod
    def get_table(text):
        bs = BeautifulSoup(text, 'lxml')
        n_rows = len(bs.find_all("tr"))
        df = pd.DataFrame(index=range(0, n_rows), columns=['date', 'open', 'close'])
        row_marker = 0
        for row in bs.find_all("tr"):
            column_marker = 0
            columns = row.find_all("td")
            for column in columns[:-1]:
                df.iat[row_marker, column_marker] = column.get_text().strip()
                column_marker += 1
            row_marker += 1
        for col in df:
            try:
                df[col] = df[col].astype(float)
            except ValueError:
                pass
        return df

    def run(self):
        self.ajax_token_finder()
        new_url = self.url_generator()
        content = self.get_content(new_url)
        return DataCrawler.get_table(content)

    @staticmethod
    def get_links(soup):
        result = []

        for string in list(map(str, soup.find_all('table')[1].find_all('td'))):
            if "href" in string:
                result.append(string.strip())
        historic_data_lst = []
        bond_info_lst = []
        names = []
        for val in result:
            index = val.find("href=")
            index += 12
            href = ""
            while val[index] != "\"":
                href += val[index]
                index += 1
            historic_data_lst.append("https://markets.businessinsider.com/bond/historical/" + href)
            bond_info_lst.append("https://markets.businessinsider.com/bonds/" + href)
            names.append(href[-12:])
        return names, historic_data_lst, bond_info_lst


class NoAuthorizationError(Exception):
    pass


def main():
    url = "https://markets.businessinsider.com/bonds/finder?borrower=71&maturity=midterm&yield=&bondtype=2%2c3%2c4%2c16&coupon=&currency=184&rating=&country=19"
    soup = BeautifulSoup(requests.get(url, headers=browser_header).content, 'lxml')
    names, historic_data_lst, bond_info_lst = DataCrawler.get_links(soup)
    for link, name in dict(zip(bond_info_lst, names)).items():
        crawler = DataCrawler(link)
        df = crawler.get_bond_info(requests.get(link, headers=browser_header).content)
        # print(df)
        df.to_csv(name + 'info' + '.csv')


if __name__ == '__main__':
    main()

