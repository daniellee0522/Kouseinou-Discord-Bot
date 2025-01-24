<h1> <img src="https://i.imgur.com/4Lgok1j.png"
  width="128"
  height="128"
  style="float:top;">

# 高性能bot (Kouseinou bot)
[![Discord Bot Status](https://img.shields.io/badge/Verified-✓%20BOT-%235865F2?style=flat-square&logo=Discord&logoColor=FFFFFF)](https://discord.com/discovery/applications/1243841697637601310)
[![Discord Bot Install count](https://img.shields.io/badge/dynamic/json?url=https://enderdaniel.work/server_count&query=$.server_count&label=高性能bot&suffix=%20servers&color=%235865F2&logo=Discord&style=flat-square&logoColor=FFFFFF)](https://discord.com/discovery/applications/1243841697637601310)
[![Discord Bot server](https://img.shields.io/discord/1263477574785564703?label=Support%20server&style=flat-square&logo=Discord&logoColor=FFFFFF)](https://discord.gg/ERSk9sYWyP)
![License](https://img.shields.io/badge/License-MIT-orange?style=flat-square&logo=License&logoColor=FFFFFF)


This is a discord bot inspired by [ermiana](https://github.com/canaria3406/ermiana).
The bot provides richer embeds preview of `nhentai.net`, `wnacg.com`, and `18comic.vip`. 

On top of that, this bot also provides functions like anime update notifications (data from [anigamer.com.tw](https://ani.gamer.com.tw), a site in Taiwan that provides anime content), and has a mini game that can simulate gacha to test your luck.

## Discord server
[https://discord.gg/ERSk9sYWyP](https://discord.gg/ERSk9sYWyP)

Any suggestions or issues can be asked here.

## Bot invite link
[https://discord.com/discovery/applications/1243841697637601310](https://discord.com/discovery/applications/1243841697637601310)

The bot is currently hit the limit of 100 servers, I will try to apply the approval for the privilege intents in some day.

## Policies
- [Terms of services](https://github.com/daniellee0522/Kouseinou-Discord-Bot/blob/main/docs/Terms_of_service.md)
- [Private policy](https://github.com/daniellee0522/Kouseinou-Discord-Bot/blob/main/docs/Privacy_policy.md)

## Functions
### Embed preview
&emsp;&emsp;When the bot detect the vaild links of `nhentai.net`, `wnacg.com`, or `18comic.vip`, it will generate the embed with richer previews of the site.
#### screenshots

![image](https://i.imgur.com/07vfj6h.png)

![image](https://i.imgur.com/eU74DDa.png)

![image](https://i.imgur.com/YJMhBa4.png)

Or you can use the command `/nhentai` `/wnacg` `/jm` and type in the digit to get previews.

Use `/解析網頁開關` to set that if bot should provide the embeds or not.

### Anime update
&emsp;&emsp;You can check the what animes you can subscribe by `/新番列表`, and subscribe them with `/訂閱` or `/查詢新番`

![image](https://i.imgur.com/B5oBv5V.png)

![image](https://i.imgur.com/1pm5vhR.png)

Use `/設定頻道` to set a channel where you want to receive update notifications.

When the anime is updated, the bot will send message like this:

![image](https://i.imgur.com/cCWWAat.png)

You can also use `/訂閱列表` to check the animes you subscribed, and `/取消訂閱 <anime_name>` to unsubscribe the anime anytime you want.

### Gacha
&emsp;&emsp;This is a simple funtion that when you type in `-1200` in chat, the bot will send gacha message like this:

![image](https://i.imgur.com/klAeQCZ.png)

Use `/統計` to see the stat of your gacha results and `/歸零` to empty your stat.

![image](https://i.imgur.com/X5b6jFl.png)

If you are the admin of the server and want to forbid this function in specific channel, use `/上鎖`.

### Welcome message
&emsp;&emsp;You can customize a welcome message with the bot by using `/歡迎訊息`, and when a member join in, the bot will send the message you have set.

### Earthquake alarm in Taiwan (optional)
&emsp;&emsp;This function is not available in the public bot. However, you can deploy a bot yourself and use this function to send messages to your server when the earthquake is about to happen.

![image](https://i.imgur.com/V7VxXmL.png)

&emsp;&emsp;Follow the steps bellow to deploy the function yourself:
 - Put your channel ids into the `alert.json`
 - Install `g++`
 - Run

 ```terminal
 cd location/of/the/file
 ```

 - Run 
 ```terminal
 g++ main.cpp -o main
 ```
 You will see a file `main` in the location you specified. Put the file under the `/main` folder.

 After that, Install 地牛 Wake UP! in your computer.

 At `setting > others`, set the collaboration to your file directory.

 ![image](https://i.imgur.com/z1Kxj6T.png)

 You can test the function by pressing the `測試` button when the bot is on.
