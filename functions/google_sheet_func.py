import gspread
import datetime
import numpy as np
import io
import os
import sys
from pathlib import Path
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
from matplotlib.font_manager import FontProperties
sys.path.insert(0, str(Path(__file__).parent.parent))
import config
gc = gspread.service_account(filename=r'./api.json')
plt.rcParams['font.sans-serif'] = ['Microsoft JhengHei']
plt.rcParams['axes.unicode_minus'] = False

# Open a sheet from a spreadsheet in one go
wks = gc.open("YT_PR_pro").get_worksheet(0)


def update_sheet(date):  # 更新表單
    col_9_values = wks.col_values(9)
    fee = x = wks.cell(3, 2).value
    fee = int(fee[3:])
    # print(col_8_values)
    if len(col_9_values) == 1:
        accu_monney = fee
    else:
        str_money = col_9_values[-1][3:]
        str_money = str_money.replace(",", "")
        print(str_money)
        accu_money = int(float(str_money))+fee

    last_row_index = len(col_9_values)
    month = last_row_index
    next_row_index = last_row_index + 1
    # print(next_row_index)
    # add a value to cell B(next_row_index)
    wks.update_cell(next_row_index, 3, date)
    wks.update_cell(next_row_index, 4, 'ㄐㄐ')
    wks.update_cell(next_row_index, 5, 'NP')
    wks.update_cell(next_row_index, 6, 'NP')
    wks.update_cell(next_row_index, 7, 'NP')
    wks.update_cell(next_row_index, 8, 'NP')
    wks.update_cell(next_row_index, 9, accu_money)
    wks.update_cell(2, 2, f'已訂閱{month}個月')
    return


def check_sheet(name):  # 查看應繳費用
    dict_ = config.SHEET_USER_COLUMNS_CHECK
    try:
        output = wks.col_values(2)
        # print(output)
        return output[dict_[name]]
    except KeyError:
        return "名字錯誤"


def get_data():  # 獲得繪製圖表的數字
    # print("test")
    x_lst = []
    y_lst = []
    for i in range(7, 11):
        x = wks.cell(i, 1).value
        # print(x)
        y = dollar_to_int(wks.cell(i, 2).value)
        x_lst.append(x)
        y_lst.append(y)
    return [x_lst, y_lst]


def currency_ticks(x, pos):
    if x >= 0:
        return 'NT${:,.0f}'.format(x)
    else:
        return '-NT${:,.0f}'.format(abs(x))


def create_bar_chart():
    plt.clf()
    font_path = './NotoSansCJKtc-Bold.otf'
    font_prop = FontProperties(fname=font_path, weight='bold')
    # minus_count = 0
    res = get_data()
    # print(res)
    # print(res)

    fig, ax = plt.subplots()
    ax.set_axisbelow(True)
    colors = ['mediumaquamarine' if e >= 0 else 'indianred' for e in res[1]]
    ax.bar(res[0], res[1], color=colors, width=0.6)
    ax.set_xticklabels(res[0], fontproperties=font_prop,
                       fontsize=15, color='dimgrey')
    setlim = False
    if max(res[1]) < 100 and min(res[1]) > -100:
        setlim = True

    if 0 < max(res[1]) < 50 and setlim == True:
        upper_bound = 50
    else:
        upper_bound = (int(max(res[1]) / 100) + 1) * 100

    if min(res[1]) < 0:
        # print("test1")
        if not setlim:
            # print("test2")
            lower_bound = (int(min(res[1]) / 100) - 1) * 100
        else:
            # print("test3")
            if min(res[1]) > -50:
                lower_bound = -50
            else:
                lower_bound = (int(min(res[1]) / 100) - 1) * 100
    else:
        lower_bound = 0

    # print(upper_bound)
    # print(lower_bound)
    # plt.grid(axis = 'y',color = 'lightgrey', linewidth = 0.75, zorder = 3)
    ax.set_ylim(lower_bound, upper_bound)
    if not setlim:
        ax.set_yticks(np.arange(lower_bound, upper_bound + 100, 100))
    # else:
        # ax.set_ylim(min(res[0]) - 10,max(res[0]) + 10)
    ax.yaxis.grid(color='lightgray',  linewidth=1)
    tick = mtick.FuncFormatter(currency_ticks)
    ax.yaxis.set_major_formatter(tick)

    plt.title("個人應繳金額", fontproperties=font_prop, fontsize=20, color='dimgray')
    plt.tick_params(left=False)
    plt.tick_params(bottom=False)
    # plt.ylabel("金額")
    # plt.bar(res[0], res[1])

    for i, v in enumerate(res[1]):
        if '-' in str(v):
            ax.text(i, 0, f"-NT${abs(v)}", ha="center", va="bottom",
                    fontproperties=font_prop, fontsize=16, color='indianred')
            # minus_count += 1
        else:
            ax.text(i, v, f"NT${v}", ha="center", va="bottom",
                    fontproperties=font_prop, fontsize=16, color='mediumaquamarine')

    plt.axhline(0, c='dimgray', lw=1)

    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_visible(False)
    ax.spines['bottom'].set_linewidth(1)
    if min(res[1]) < 0:
        ax.spines['bottom'].set_color('lightgray')
    else:
        ax.spines['bottom'].set_color('dimgray')

    buffer = io.BytesIO()
    plt.savefig(buffer, format='png')
    buffer.seek(0)
    # print(122)
    return buffer


def pay(money, name):
    dict_ = config.SHEET_USER_COLUMNS_PAY
    try:
        col = wks.col_values(dict_[name])
        # print(row)
        if dict_[name] == 3:
            return "無須繳費"
        else:
            # print("con")
            # print(row)
            if col[-1] != "NP":
                update_chart = dollar_to_int(col[-1])

                if update_chart+money == 0:
                    wks.update_cell(len(col), dict_[name], 'NP')
                else:
                    wks.update_cell(len(col), dict_[name], update_chart+money)
            else:
                wks.update_cell(len(col), dict_[name], money)

            return "完成繳費"

    except KeyError:
        return "名字錯誤"


def get_current_date():  # 獲取當前日期 格式:(MM/DD) str
    month_date = str(datetime.datetime.today())
    date_sort = month_date[5:7]+'/'+month_date[8:10]
    return date_sort


def check_date():  # 確認當前日期是否是28號
    month_date = str(datetime.datetime.today())
    date = int(month_date[8:10])
    if date == 28:
        return True
    else:
        return False


def dollar_to_int(ntdollar):  # 轉換'+-NT$'字串為int格式
    if '-' in ntdollar:
        money = ntdollar[4:]
        money = -int(float(money.replace(',', "")))
    else:
        money = ntdollar[3:]
        money = int(float(money.replace(',', "")))

    return money


def how_far_from_zero():  # 離零點有多少秒
    currentTime = str(datetime.datetime.now().strftime("%H:%M:%S"))
    hour = int(currentTime[0:2])
    min = int(currentTime[3:5])
    sec = int(currentTime[6:])
    sec_sort = hour*3600+min*60+sec
    output = 86400-sec_sort
    return output

# wks.update_cell(10, 8, "NP")

# print(how_far_from_zero())
