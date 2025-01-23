import json
import requests
from bs4 import BeautifulSoup


#return = [動畫名,動畫集數,播放網址,動畫縮圖]
def anime_get_info(input_name,R_18="n"):
    input_name = input_name.lower()
    search_lst = []
    headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.45 Safari/537.36',
}
    r = requests.get('https://ani.gamer.com.tw/', headers=headers)
    if r.status_code == 200:
        soup = BeautifulSoup(r.text, 'html.parser')
        newanime_item = soup.select_one('.timeline-ver > .newanime-block')
        anime_items = newanime_item.select('.newanime-date-area:not(.premium-block)')

        # 依序針對每個動畫區塊擷取資料
        for anime_item in anime_items:
            try:
                anime_name = anime_item.find('p', class_='anime-name').text.strip()
                anime_name2 = anime_name.lower()
            except:
                continue
            if input_name in anime_name2:
                if R_18 == "R" or R_18 == "r":
                    try:
                         anime_tag=anime_item.select_one('.anime-label-block>span').text.strip()
                         if anime_tag == "年齡限制":
                            anime_name = anime_name + "(年齡限制)"
                    except:
                        continue
                search_lst.append(anime_name)
                anime_episode = anime_item.select_one('.anime-episode').text.strip()
                search_lst.append(anime_episode)
                anime_href = anime_item.select_one('a.anime-card-block').get('href')
                search_lst.append('https://ani.gamer.com.tw/'+anime_href)
                anime_image = anime_item.select_one('.lazyload').get('data-src')
                search_lst.append(anime_image)
                return search_lst
            else:
                continue 
        return search_lst    
    else:
        print(f'請求失敗：{r.status_code}')
        return "fail to connect"

#return = [動畫名,動畫集數,星期幾更新,幾點更新]
def anime_get_info_add(input_name,server_id,R_18="n"):
    input_name = input_name.lower()
    with open('json/sub.json',encoding = "utf8") as f :
        data= json.load(f)
    week_lst=["一","二","三","四","五","六","日"]
    try:
        if data[str(server_id)] != []:  
            for dict in data[str(server_id)]:
                if input_name in dict["name"]:
                    if R_18 == "y":
                        if input_name+"(年齡限制)" == dict["name"] :
                            continue
                        elif input_name == dict["name"]+"(年齡限制)":
                            continue
                    elif R_18 == "r" or R_18 == "R":
                        if "(年齡限制)" not in dict["name"]:
                             continue
                        else:
                            return "repeated"
                    else:
                        if "(年齡限制)" in dict["name"]:
                            continue
                        else:
                            return "repeated"
    except KeyError:
        pass
    headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.45 Safari/537.36',
    }
    r = requests.get('https://ani.gamer.com.tw/', headers=headers)
    if r.status_code == 200:
        #print(f'請求成功：{r.status_code}')
        soup = BeautifulSoup(r.text, 'html.parser')
        newanime_item = soup.select_one('.timeline-ver > .newanime-block')
        anime_items = newanime_item.select('.newanime-date-area:not(.premium-block)')

        # 依序針對每個動畫區塊擷取資料
        for anime_item in anime_items:
            try:
                anime_name = anime_item.find('p', class_='anime-name').text.strip()
                anime_name2 = anime_name.lower()
            except:
                continue
            if R_18 == "r" or R_18=="R":
                try:
                    anime_tag=anime_item.select_one('.anime-label-block>span').text.strip()
                    if anime_tag == "年齡限制":
                        anime_name= anime_name + "(年齡限制)"
                except:
                    continue
            else:
                try:
                    anime_tag=anime_item.select_one('.anime-label-block>span').text.strip()
                    if anime_tag == "年齡限制":
                        anime_name= anime_name + "(年齡限制)"
                except:
                    pass
            if input_name in anime_name2:
                anime_episode = anime_item.select_one('.anime-episode').text.strip()
                anime_update_time = anime_item.select_one('.anime-hours-block>span').text.strip()
                anime_update_date = anime_item.select_one('.newanime-date-area>span').text.strip()
                anime_formed_time = anime_update_time.replace(":","")
                try:
                    anime_formed_date=week_lst.index(anime_update_date[anime_update_date.index(')')-1:anime_update_date.index(')')])+1
                except ValueError:
                    continue
                d={
                    "name" : anime_name,
                    "episode" : anime_episode,
                    "update_date" : anime_formed_date,
                    "update_time" : anime_formed_time
                 }
                try:
                    data[str(server_id)].append(d)
                except KeyError:
                    data[str(server_id)]=[]
                    data[str(server_id)].append(d)
                with open('json/sub.json',"w",encoding = "utf8") as f:
                    json.dump(data,f,ensure_ascii=False,indent = 4)
                    return anime_name
            else:
                continue
        return "not found"
    else:
        print(f'請求失敗：{r.status_code}')
        return

#return = [動畫名,動畫集數,播放網址]
def anime_lst():
    search_lst = []
    headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.45 Safari/537.36',
    }
    r = requests.get('https://ani.gamer.com.tw/', headers=headers)
    if r.status_code == 200:
        #print(f'請求成功：{r.status_code}')
        soup = BeautifulSoup(r.text, 'html.parser')
        newanime_item = soup.select_one('.timeline-ver > .newanime-block')
        anime_items = newanime_item.select('.newanime-date-area:not(.premium-block)')

        # 依序針對每個動畫區塊擷取資料
        for anime_item in anime_items:
            temp=[]
            try:
                anime_name = anime_item.find('p', class_='anime-name').text.strip()
            except:
                continue
            try:
                anime_tag=anime_item.select_one('.anime-label-block>span').text.strip()
                if anime_tag == "年齡限制":
                    anime_name = anime_name+"(年齡限制)"
            except:
                pass
            temp.append(anime_name)
            #print(anime_name)
            anime_episode = anime_item.select_one('.anime-episode').text.strip()
            temp.append(anime_episode)
            #print(anime_episode)
            anime_href = anime_item.select_one('a.anime-card-block').get('href')
            temp.append('https://ani.gamer.com.tw/'+anime_href)
            #print('https://ani.gamer.com.tw/'+anime_href)
            anime_update_time = anime_item.select_one('.anime-hours-block>span').text.strip()
            anime_update_date = anime_item.select_one('.newanime-date-area>span').text.strip()
            try:
                temp.append('星期'+anime_update_date[anime_update_date.index(')')-1:anime_update_date.index(')')])
            except ValueError:
                continue
            temp.append(anime_update_time)
            search_lst.append(temp)
        return search_lst     #[動畫名,目前集數,網址,星期幾,幾點]
    else:
        print(f'請求失敗：{r.status_code}')
        return "fail to connect"

def check_and_update(index,server_id):         #判斷動畫是否更新
    week_lst=["一","二","三","四","五","六","日"]
    with open('json/sub.json','r',encoding='utf8') as f:
        data=json.load(f)
    headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.45 Safari/537.36',
    }
    try:
        r = requests.get('https://ani.gamer.com.tw/', headers=headers)
        if r.status_code == 200:
            #print(f'請求成功：{r.status_code}')
            soup = BeautifulSoup(r.text, 'html.parser')
            newanime_item = soup.select_one('.timeline-ver > .newanime-block')
            anime_items = newanime_item.select('.newanime-date-area:not(.premium-block)')
            for anime_item in anime_items:
                try:
                    anime_name = anime_item.find('p', class_='anime-name').text.strip()
                except:
                    continue
                try:
                    anime_tag = anime_item.select_one('.anime-label-block>span').text.strip()
                    if anime_tag == "年齡限制":
                        anime_name = anime_name+"(年齡限制)"
                except:
                    pass
                if anime_name == data[str(server_id)][index]["name"]:
                    anime_episode = anime_item.select_one('.anime-episode').text.strip()
                    if anime_episode != data[str(server_id)][index]["episode"]:
                        lst=[]
                        anime_href = 'https://ani.gamer.com.tw/'+anime_item.select_one('a.anime-card-block').get('href')
                        anime_image = anime_item.select_one('.lazyload').get('data-src')
                        
                        anime_update_time = anime_item.select_one('.anime-hours-block>span').text.strip()
                        anime_update_date = anime_item.select_one('.newanime-date-area>span').text.strip()
                        anime_formed_time = anime_update_time.replace(":","")
                        try:
                            anime_formed_date=week_lst.index(anime_update_date[anime_update_date.index(')')-1:anime_update_date.index(')')])+1
                        except:
                            continue
                        lst.append(anime_episode)
                        lst.append(anime_href)
                        lst.append(anime_image)

                        with open('json/sub.json','r',encoding='utf8') as f:
                            data=json.load(f)
                        data[str(server_id)][index]["update_date"] = anime_formed_date
                        data[str(server_id)][index]["update_time"] = anime_formed_time
                        data[str(server_id)][index]["episode"] = anime_episode
                        with open('json/sub.json','w',encoding='utf8') as f:
                            json.dump(data,f,ensure_ascii=False,indent = 4)
                        return lst
                    else:
                        return "already updated"
                else:
                    continue
        data[str(server_id)].pop(index)
        if data[str(server_id)] == []:
            data.pop(str(server_id))
        with open('json/sub.json','w',encoding='utf8') as f:
            json.dump(data,f,ensure_ascii=False,indent = 4)
        return "no more update"
    except:
        return "fail to connect"
    

if __name__ == "__main__":
    print(anime_get_info("ave"))