import bs4
import urllib.request as req
from urllib.parse import quote
import requests
import pandas as pd


def getdata(url=None, pages=None, kw=None):

    push_lst = []
    board_lst = []
    author_lst = []
    board_lst = []
    title_lst = []
    date_lst = []
    url_lst = []
    content_lst = []

    n = 0

    while True:
        # lst+=("------ <第"+str(n+1)+"頁資料>------\n")

        request = req.Request(url, headers={
            "cookie": "over18=1",
            "user-agent": "Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/87.0.4280.88 Mobile Safari/537.36"
        })

        with req.urlopen(request) as response:
            data = response.read().decode("utf-8")
        root = bs4.BeautifulSoup(data, "html.parser")
        # titles=root.find_all("div",class_="title")
        titles = root.select("div.title")

        for title in titles:
            if title.a != None and kw in title.a.get_text():

                # lst+=title.a.string+"\n"
                url = "https://www.ptt.cc"+title.a["href"]

                my_headers = {"cookie": "over18=1",
                              "user-agent": "Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/87.0.4280.88 Mobile Safari/537.36"
                              }
                response2 = requests.get(url, headers=my_headers)
                soup = bs4.BeautifulSoup(response2.text, "html.parser")

                header = soup.find_all('span', 'article-meta-value')

                push = soup.find_all('div', 'push')
                author = header[0].text
                board = header[1].text
                # title = header[2].text
                date = header[3].text
                main_container = soup.find(id='main-container')
                all_text = main_container.text
                pre_text = all_text.split('--')[0]
                texts = pre_text.split('\n')
                contents = texts[2:]
                content = '\n'.join(contents)
                tmp = [i.text for i in push]
                push_lst.append(tmp)
                board_lst.append(board)
                author_lst.append(author)
                title_lst.append(title.a.get_text())
                date_lst.append(date)
                url_lst.append(url)
                content_lst.append(content)

        nextlink = root.find("a", string="‹ 上頁")
        try:
            url = str("https://www.ptt.cc"+nextlink["href"])
        except:
            break
        # print(nextlink)
        if n == pages-1:
            break
        n += 1

    df = pd.DataFrame(list(zip(title_lst, board_lst, author_lst, push_lst,
                      date_lst, url_lst)), columns=["標題", "看板", "作者", "推文內容", "日期", "網址"])
    df.to_csv('df.csv', index=False)
    return

# 測試範例
# getdata("https://www.ptt.cc/bbs/Baseball/index.html", 20, "棒球")
