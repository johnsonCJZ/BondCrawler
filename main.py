import datetime
from datetime import date
from datetime import timedelta
import numpy as np
import scipy.optimize as optimize
import pandas as pd
import matplotlib.pyplot as plt
from scipy.interpolate import spline

global par
global coup
global today
global freq
global spot_rate_data


def minus_month(time, num):
    assert 0 <= num <= 12
    year = time.year
    month = time.month
    if (month - num) / 12 < 0:
        new_month = (month - num) % 12
        carry = abs((month - num) // 12)
        return date(year - carry, new_month, time.day)
    return date(year, month - num, time.day) if (month - num) % 12 != 0 else date(year - 1, 12, time.day)


def ytm_calculator(price, par, coup_rate, issue_date, mature_date, freq=2, guess=0.04):
    """
    calculator for frequency = 2
    """
    assert issue_date < today
    global coup

    last_coupon_date, coupon_date = get_coupon_date(today, mature_date)
    price = dirty_price(coup, price, last_coupon_date, today)

    # Get each period
    dt = []
    for i in range(len(coupon_date)):
        difference = (coupon_date[i] - today).days
        dt.append(difference / 182.5)

    # Calculate ytm using newton's method
    ytm_function = lambda y: sum([coup / ((1 + y / freq) ** j) for j in dt]) + par / ((1 + y / freq) ** dt[-1]) - price
    year = (mature_date - today).days / 365
    yield_rate = optimize.newton(ytm_function, guess)
    return year, yield_rate


def dirty_price(coupon, clean_price, last_coupon_date, date_today):
    accrued_interest = (date_today - last_coupon_date).days / 182.5 * coupon
    return clean_price + accrued_interest


def extract_data(data, today):
    global coup
    coupon_rate = float(data.get("coupon")[:-1]) / 100
    issue_date = datetime.datetime.strptime(data.get("issue date"), '%m/%d/%Y').date()
    maturity_date = datetime.datetime.strptime(data.get("maturity date"), '%m/%d/%Y').date()
    string_date = today.strftime("%m/%d/%Y")
    date = string_date[1:3] + string_date[4:] if string_date[3] == "0" else string_date[1:]
    price = float(data.get(date))
    coup = coupon_rate / freq * par
    return price, coupon_rate, issue_date, maturity_date


def get_coupon_date(date_today, maturity_date):
    """
    precondition: issue date is before today
    """
    date = minus_month(maturity_date, 6)
    coupon_date = [maturity_date]
    while date > date_today:
        coupon_date.append(date)
        date = minus_month(date, 6)
    coupon_date.reverse()
    return date, coupon_date


def dictionary_to_lists(dictionary):
    year = []
    rate = []
    for key, value in dictionary.items():
        year.append(key)
        rate.append(value)
    return year, rate


def convert_year_to_period(date_lst):
    result = []
    for i in date_lst:
        result.append((i - today).days / 365)
    return result


def spot_calculator(date_today, price, maturity_date, par=100):
    global spot_rate_data
    last_coupon_date, coupon_date = get_coupon_date(date_today, maturity_date)

    # remove the last coupon date
    coupon_date = coupon_date[:-1]
    price = dirty_price(coup, price, last_coupon_date, date_today)

    year, rate_lst = dictionary_to_lists(spot_rate_data)
    period_lst = convert_year_to_period(year)

    # reduce present values of previous coupons
    for date in coupon_date:
        if date in spot_rate_data:
            rate = spot_rate_data[date]
        elif min(year) <= date <= max(year):
            predict_x = (date - date_today).days/365
            rate = np.interp(predict_x, period_lst, rate_lst)
        else:
            rate = spot_rate_data[max(year)]

        period = (date - date_today).days / 365
        pv_coup = coup / np.exp(rate * period)
        price = price - pv_coup

    # calculate zero-coupon rate
    spot_rate = - np.log(price / (par + coup)) / ((maturity_date - date_today).days / 365)
    spot_rate_data[maturity_date] = spot_rate


def ytm_run(df, plot=True, smooth=False):
    year_lst = []
    yield_rate_lst = []
    for i in range(df.shape[0]):
        price, coupon_rate, issue_date, maturity_date = extract_data(df.iloc[i], today)
        year, yield_rate = ytm_calculator(price, par, coupon_rate, issue_date, maturity_date)
        year_lst.append(year)
        yield_rate_lst.append(yield_rate)
    if plot:
        if smooth:
            show_smooth_graph(year_lst, yield_rate_lst)
        else:
            plt.plot(year_lst, yield_rate_lst, label=str(today))
        # plt.show()
    return year_lst, yield_rate_lst


def show_smooth_graph(x, y):
    xnew = np.linspace(min(x), max(x), 300)
    power_smooth = spline(x, y, xnew)
    plt.plot(xnew, power_smooth, label=str(today))
    # plt.show()


def spot_run(df, today, plot=True, smooth=False):
    for i in range(df.shape[0]):
        price, coupon_rate, issue_date, maturity_date = extract_data(df.iloc[i], today)
        spot_calculator(today, price, maturity_date)
    year_lst = []
    spot_rate_lst = []
    for key, value in spot_rate_data.items():
        year_lst.append((key - today).days / 365)
        spot_rate_lst.append(value)
    if plot:
        if smooth:
            show_smooth_graph(year_lst, spot_rate_lst)
        else:
            plt.plot(year_lst, spot_rate_lst, label=str(today))


def forward_run(df, today, predict_year, plot=True, smooth=False):
    spot_run(df, today, plot=False)
    year, rate = dictionary_to_lists(spot_rate_data)
    period_lst = convert_year_to_period(year)
    first_year_spot_rate = np.interp(1, period_lst, rate)
    forward_rate_lst = []
    for y in predict_year:
        spot_rate = np.interp(y + 1, period_lst, rate)
        forward_rate_lst.append(((1 + spot_rate) ** (y + 1) / (1 + first_year_spot_rate)) ** (1 / (y)) - 1)
    if plot:
        if smooth:
            show_smooth_graph(predict_year, forward_rate_lst)
        else:
            plt.plot(predict_year, forward_rate_lst, label=str(today))
    return forward_rate_lst


if __name__ == '__main__':
    freq = 2
    spot_rate_data = {}
    par = 100
    global today
    day_lst = [date(2020, 1, i) for i in range(2, 4)] + [date(2020, 1, i) for i in range(6, 11)] + \
              [date(2020, 1, i) for i in range(13, 16)]
    plt.style.use('ggplot')
    df = pd.read_csv("apm466_data.csv")

    # ------------  ytm -----------------------------------------------------------------------------
    # for today in day_lst:
    #     ytm_run(df)
    # plt.title("Yield Curve")
    # plt.xlabel("year")
    # plt.ylabel("yield rate")
    # plt.legend()
    # plt.show()

    # ------------- spot_rate -----------------------------------------------------------------------
    # for today in day_lst:
    #     spot_run(df, today, plot=True, smooth=True)
    # plt.title("Spot Curve")
    # plt.xlabel("year")
    # plt.ylabel("spot rate")
    # plt.legend()
    # plt.show()

    # ------------- forward_rate --------------------------------------------------------------------
    predict_year = [1, 2, 3, 4]
    for today in day_lst:
        forward_run(df, today, predict_year)
    # plt.title("Forward Curve")
    # plt.xlabel("year")
    # plt.ylabel("forward rate")
    # plt.legend()
    # plt.legend()
    # plt.show()

    # -------------Question 5 -----------------------------------------------------------------------
    yield_matrix = np.zeros((10, 5))
    forward_matrix = np.zeros((10, 4))
    i = 0
    for today in day_lst:
        year_lst, yield_lst = ytm_run(df, plot=False)
        forward_rate_lst = forward_run(df, today, predict_year, plot=False)
        # print(forward_rate_lst)
        for j in range(5):
            yield_matrix[i][j] = np.interp(j+1, year_lst, yield_lst)
            if j != 4:
                forward_matrix[i][j] = forward_rate_lst[j]
        i += 1
    # print(yield_matrix)
    # print(forward_matrix)
    X = np.zeros((5, 9))
    for a in range(5):
        X[a] = np.log(yield_matrix[1:10, a] / yield_matrix[0:9, a])
    log_return_covariance = np.cov(X)
    forward_covariance = np.cov(forward_matrix.transpose())
    print("eigenvalue and eigenvector of log_return covariance:", np.linalg.eig(log_return_covariance))

    print("eigenvalue and eigenvector of forward covariance:", np.linalg.eig(forward_covariance))

    # print("log return covariance", log_return_covariance)
    # print("forward covariance", forward_covariance)


