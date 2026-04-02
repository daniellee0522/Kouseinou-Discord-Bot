import aiohttp
import asyncio
from bs4 import BeautifulSoup
import json

class Sec5sh:
    def __init__(self):
        self.cookies = {}
        self.UA = None

    async def request(self, url):
        headers = {"User-Agent": self.UA} if self.UA else {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3"}
        async with aiohttp.ClientSession(cookies=self.cookies, headers=headers) as session:
            async with session.get(url) as response:
                if response.status == 200:
                    return await response.text()
                elif response.status == 403:
                    return await self.sec5sh(url)
                
    async def read(self, url):
        headers = {"User-Agent": self.UA} if self.UA else {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3"}
        async with aiohttp.ClientSession(cookies=self.cookies, headers=headers) as session:
            async with session.get(url) as response:
                if response.status == 200:
                    return True
                else:
                    return False

    async def sec5sh(self, url):
        print("破盾中...")
        urlServer = "http://localhost:8191/v1"
        payload = {
            "cmd": "request.get",
            "url": url,
            "maxTimeout": 160000
        }
        headers = {
            'Content-Type': 'application/json'
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(urlServer, headers=headers, json=payload) as response:
                if response.status == 200:
                    data = await response.json()
                    solution = data['solution']
                    self.UA = solution['userAgent']
                    for item in solution['cookies']:
                        self.cookies[item['name']] = item['value']
                    print("破盾成功")
                    return data['solution']['response']
                print("绕过5秒盾错误！！！")
                return None




if __name__ == "__main__":
    url = "https://nhentai.net/g/433125/"
    async def test ():
        sec5sh = Sec5sh()
        response = await sec5sh.request(url)
        # soup = BeautifulSoup(response, 'html.parser')
        # soup = BeautifulSoup(html, 'html.parser')
        # a_tags = soup.find_all('a', class_=lambda x: x and 'text-secondary' in x)
        # for i, a_tag in enumerate(a_tags):
            # print(a_tag.text.strip())
            # pass

        soup = BeautifulSoup(response, 'html.parser')
        description = soup.find('meta', attrs={'name': 'description'})
        title = soup.find('meta', attrs={'property': 'og:title'})
        image = soup.find('meta', attrs={'property': 'og:image'})

        print(title['content'])
        if image:
            print(image['content'])
        if description:
            print(description['content']) 
            # print(f"{key}: {value}")
        # print(soup.prettify())
        # oup = BeautifulSoup(response, 'html.parser')
        # meta_desc = soup.find("meta", attrs={"name": "description"})
        # print(soup.prettify())
        # if meta_desc:
            # print(meta_desc['content'])
        # else:
            # print("Meta description not found.")
        # print(response)
    response = asyncio.run(test())
    import requests

