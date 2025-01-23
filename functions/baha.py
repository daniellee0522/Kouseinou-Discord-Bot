import re
from requests_html import HTMLSession
import bs4
import urllib.request as req
import requests
import pandas as pd
import discord
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
import os


USERNAME = os.getenv("baha_username")
PASSWORD = os.getenv("baha_password")


class Conf:
    def __init__(self, project_name):
        self.project_name = project_name
        self.config = {}

    def set(self, key, value):
        self.config[key] = value

    def get(self, key):
        return self.config.get(key)


def config_manager():
    # Return a dictionary with the necessary configuration
    return {
        'BHUD': f'{USERNAME}',
        'BHPD': f'{PASSWORD}'
    }


def is_baha(url):
    parsed_url = urlparse(url)
    query_params = parse_qs(parsed_url.query)
    if 'bsn' in query_params and "https://forum.gamer.com.tw" in url:
        if query_params['bsn'] == ['60076']:
            return True
        else:
            return False
    else:
        return False


def reset_page_param(url):
    # 解析URL
    parsed_url = urlparse(url)

    # 解析查詢參數
    query_params = parse_qs(parsed_url.query)

    # 修改page參數
    if 'page' in query_params:
        query_params['page'] = ['1']

    # 構建新的查詢字符串
    new_query_string = urlencode(query_params, doseq=True)

    # 構建新的URL
    new_url = urlunparse(parsed_url._replace(query=new_query_string))

    return new_url


def reload_baha_tk(sac_bh):
    session = HTMLSession()
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded',
        'Cookie': 'ckAPP_VCODE=9487',
    }

    config = config_manager()
    data = 'uid=' + config['BHUD'] + '&passwd=' + \
        config['BHPD'] + '&vcode=9487'

    try:
        response = session.post(
            'https://api.gamer.com.tw/mobile_app/user/v3/do_login.php',
            headers=headers,
            data=data,
            timeout=2.5
        )

        response.raise_for_status()
        cookies = response.cookies

        if 'BAHAENUR' in cookies:
            sac_bh.set('BAHAENUR', cookies['BAHAENUR'])
        if 'BAHARUNE' in cookies:
            sac_bh.set('BAHARUNE', cookies['BAHARUNE'])

    except requests.HTTPError as http_err:
        print(f'baha api HTTP error: {http_err}')
        print(f'Response status code: {http_err.response.status_code}')
        # print(f'Response headers: {http_err.response.headers}')
        print(f'Response text: {http_err.response.text}')
    except requests.RequestException as req_err:
        print(f'baha api request error: {req_err}')


def bahaog(url, BAHAENUR, BAHARUNE, sac_bh):
    new_url = reset_page_param(url)
    try:
        try:
            request = req.Request(new_url, headers={
                "cookie": 'BAHAENUR=' + BAHAENUR + '; BAHARUNE=' + BAHARUNE + ';',
                "user-agent": "Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/87.0.4280.88 Mobile Safari/537.36"
            })
        except:
            reload_baha_tk(sac_bh)
            BAHAENUR = sac_bh.get('BAHAENUR')
            BAHARUNE = sac_bh.get('BAHARUNE')
            request = req.Request(new_url, headers={
                "cookie": 'BAHAENUR=' + BAHAENUR + '; BAHARUNE=' + BAHARUNE + ';',
                "user-agent": "Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/87.0.4280.88 Mobile Safari/537.36"
            })

        with req.urlopen(request) as response:
            data = response.read().decode("utf-8")
        soup = bs4.BeautifulSoup(data, "html.parser")
        title = soup.select_one('meta[property="og:title"]').get('content')
        embed = discord.Embed(title=title, url=url)
        embed.set_author(name="巴哈姆特電玩資訊站")
        # print(title)
        try:
            description = soup.select_one(
                'meta[property="og:description"]').get('content')
            embed.description = description
        except AttributeError:
            pass
        try:
            thumbnail = soup.select_one(
                'meta[property="og:image"]').get('content')
            embed.set_thumbnail(url=thumbnail)
        except AttributeError:
            pass

        return embed
    except:
        reload_baha_tk(sac_bh)
        BAHAENUR = sac_bh.get('BAHAENUR')
        BAHARUNE = sac_bh.get('BAHARUNE')
        request = req.Request(new_url, headers={
                "cookie": 'BAHAENUR=' + BAHAENUR + '; BAHARUNE=' + BAHARUNE + ';',
                "user-agent": "Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/87.0.4280.88 Mobile Safari/537.36"
            })

        with req.urlopen(request) as response:
            data = response.read().decode("utf-8")
        soup = bs4.BeautifulSoup(data, "html.parser")
        title = soup.select_one('meta[property="og:title"]').get('content')
        embed = discord.Embed(title=title, url=url)
        embed.set_author(name="巴哈姆特電玩資訊站")
        try:
            description = soup.select_one(
                'meta[property="og:description"]').get('content')
            embed.description = description
        except AttributeError:
            pass
        try:
            thumbnail = soup.select_one(
                'meta[property="og:image"]').get('content')
            embed.set_thumbnail(url=thumbnail)
        except AttributeError:
            pass
        return embed


def extract_urls(text):
    # 定義正則表達式模式來匹配URL
    url_pattern = re.compile(r'(https?://[^\s]+)')

    # 使用正則表達式查找所有匹配的URL
    urls = re.findall(url_pattern, text)

    return urls
