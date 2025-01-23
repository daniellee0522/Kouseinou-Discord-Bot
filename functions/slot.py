import random
import json
def Gacha(SSR,SR,R,PU=[],time=10): #三星、二星、一星、PU率(可能有多PU)、次數
    #amount=[]
    type_=[]
    type_.append(R)
    type_.append(SR)
    for i in range(len(PU)):
        PU[i] = round(PU[i],6)
        SSR = SSR-PU[i] #PU另計

    SSR = round(SSR,6)
    type_.append(SSR)
    for i in PU:
        type_.append(i)
    number = [i+1 for i in range(len(type_))]
    random_num = random.choices(number,type_,k=9)
    number.pop(0)
    type_.pop(0)
    type_[0] = R+SR
    random_num.append(random.choices(number,type_)[0])
    return random_num

def lock_channel(channel_id):
    with open ('json/lock.json','r', encoding = 'utf8') as file:
        data=json.load(file)
    if channel_id not in data:
        data.append(channel_id)
        with open('json/lock.json','w',encoding='utf8') as f:
            json.dump(data,f,ensure_ascii=False,indent = 4)
        return "locked"
    else:
        return "already locked"
    
def unlock_channel(channel_id):
    with open ('json/lock.json','r', encoding = 'utf8') as file:
        data=json.load(file)
    if channel_id not in data:
        return "not locked"
    else:
        data.remove(channel_id)
        with open('json/lock.json','w',encoding='utf8') as f:
            json.dump(data,f,ensure_ascii=False,indent = 4)
        return "unlocked"
    
def check_lock(channel_id):
    with open ('json/lock.json','r', encoding = 'utf8') as file:
        data= json.load(file)
    if channel_id in data:
        return True
    else:
        return False