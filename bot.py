import json
import asyncio
import random
import os
import discord
import time
import json
import logging
from discord.ext import commands
from discord import app_commands
from functions.slot import Gacha, check_lock
from functions.baha import *
from functions.nhentai import *
from functions.wnacg import *
from functions.embed_permission import *
from functions.jm import *

logging.basicConfig(level=logging.INFO)
intents = discord.Intents.default()
intents.messages=True
intents.message_content = True
intents.guilds=True
intents.presences = True
intents.members = True
bot = commands.Bot(command_prefix='$', intents=intents)
bot.remove_command('help')

sac_bh = Conf('sacPY')
reload_baha_tk(sac_bh)

owner_id = os.getenv("owner_id")

@bot.event
async def on_ready():
    bot.add_view(NumberView())
    bot.add_view(NumberView2())
    bot.add_view(NumberView3())

    try:
        synced = await bot.tree.sync()

        print(">>Bot is online<<")
        print(f'Synced {len(synced)} commands.')
        await bot.change_presence(activity=discord.Game("ATRI -My Dear Moments-"))
    except Exception as e:
        print(f'Failed to sync commands: {e}')


@bot.tree.command(name="help", description="提供指令的簡介")
async def help(interaction: discord.Interaction):
    count = 0
    await interaction.response.defer()
    for cog_name, cog in bot.cogs.items():
        if cog.__cog_app_commands__ == []:
            continue
        if cog_name == "動畫瘋指令":
            embed = discord.Embed(
                title=f"{cog_name}", description="動畫瘋自動通知的相關指令。", color=0x5568)
            embed.set_author(
                name="巴哈姆特動畫瘋", icon_url="https://i.imgur.com/RF7sMkY.png")
        elif cog_name == "抽卡指令":
            embed = discord.Embed(
                title=f"{cog_name}", description="模擬抽卡的相關指令，輸入-1200進行抽卡。", color=3447003)
            embed.set_author(
                name="ブルーアーカイブ", icon_url="https://i.imgur.com/R1bu6V6.jpg")
        elif cog_name == "關鍵字指令":
            embed = discord.Embed(title=f"{cog_name}", color=15548997)
        elif cog_name == "表單指令":
            if interaction.guild_id != 927850351703506954:
                continue
            embed = discord.Embed(
                title=f"{cog_name}(僅適用於卡.伺服器)", description="", color=0x2ecc71)
            embed.set_author(name="Google Sheet",
                             icon_url="https://i.imgur.com/FTxIgMA.png")
        elif cog_name == "分帳指令":
            embed = discord.Embed(title=f"{cog_name}")
        else:
            embed = discord.Embed(title=f"{cog_name}")

        for object in cog.__cog_app_commands__:
            embed.add_field(name=object.name,
                            value=object.description, inline=False)

        if count == 0:
            await interaction.followup.send(embed=embed)
            count += 1
        else:
            await interaction.channel.send(embed=embed)
            
@bot.tree.context_menu(name="刪除訊息")
async def delete_messenge(interaction: discord.Interaction, message: discord.Message):
    if message.author.id == bot.user.id:
        await message.delete()
        await interaction.response.send_message("已刪除", ephemeral=True)
    else:
        await interaction.response.send_message("只能刪除此機器人的訊息", ephemeral=True)

COOLDOWN_AMOUNT = 1.5  # seconds
last_executed = time.time()


def assert_cooldown():
    global last_executed 
    if last_executed + COOLDOWN_AMOUNT < time.time():
        last_executed = time.time()
        return True
    return False


@bot.tree.command(name="cookies", description="更新cookies(你沒權限)")
@app_commands.describe(cf_clearance="cookie1", csrftoken="cookie2")
async def cookies(interaction: discord.Interaction, cf_clearance: str, csrftoken: str):
    if interaction.user.id != int(owner_id):
        await interaction.response("你沒有權限使用此指令")
    else:
        dict_ = {"cf_clearance": cf_clearance, "csrftoken": csrftoken}
        with open('json/cookies.json', 'w', encoding='utf8') as f:
            json.dump(dict_, f, ensure_ascii=False, indent=4)


@bot.tree.command(name="wnacg", description="回傳wnacg embed")
@app_commands.describe(digit="神秘數字")
async def wnacg(interaction: discord.Interaction, digit: int):
    digit = str(digit)
    embed = create_wnacg_embed(digit=digit)
    if embed == 404:
        await interaction.response.send_message("不存在")
        return
    elif embed == 403:
        await interaction.response.send_message("存取遭拒")
        return
    view = NumberView2(embed=embed)
    await interaction.response.send_message(embed=embed, view=view)

@bot.tree.command(name="jm", description="回傳禁漫天堂 embed")
@app_commands.describe(digit="神秘數字")
async def jm(interaction: discord.Interaction, digit: int):
    
    url = f"https://18comic.vip/album/{digit}/"
    try:
        embed = jm_embed(url)
        view3 = NumberView3(embed=embed)
        await interaction.response.send_message(embed=embed, view=view3)
        channel = interaction.guild.get_channel(1294356961202147439)
        await channel.send(f"https://enderdaniel.work/transform?url={url}")
    except:
        await interaction.response.send_message("不存在或存取遭拒")
        
        
@bot.tree.command(name="nhentai", description="回傳nhentai embed")
@app_commands.describe(digit="神秘數字")
async def nh(interaction: discord.Interaction, digit: int):
    digit = str(digit)
    with open('json/cookies.json', 'r', encoding='utf8') as file:
        data = json.load(file)
    cf_clearance = data["cf_clearance"]
    csrftoken = data["csrftoken"]
    embed = test_embed(
        digit=digit, cf_clearance=cf_clearance, csrftoken=csrftoken)
    if embed == 404:
        await interaction.response.send_message("不存在")
        return
    elif embed == 403:
        await interaction.response.send_message("存取遭拒")
        return
    view = NumberView(embed=embed)
    await interaction.response.send_message(embed=embed, view=view)


@bot.event
async def on_member_join(member):
    server_id = str(member.guild.id)
    print("Somebody joined")
    with open('json/welcome.json', 'r', encoding='utf8') as file:
        data = json.load(file)
    if server_id in list(data.keys()):
        message = data[server_id][0]
        channel = bot.get_channel(data[server_id][1])
        await asyncio.sleep(1)
        await channel.send(message)
    else:
        name = member.guild.name
        await member.send(f"歡迎來到{name}伺服器")


@bot.event
async def on_message(msg):
    pattern = r'\|\|.*?\|\|'
    clean_text = re.sub(pattern, '', msg.content)
    urls = extract_urls(clean_text)
    if urls != []:
        for url in urls:
            if is_baha(url):
                try:
                    server_id = msg.guild.id
                except:
                    server_id = None
                if is_embed_ban(server_id=server_id, arg="baha"):
                    continue
                BAHAENUR = sac_bh.get('BAHAENUR')
                BAHARUNE = sac_bh.get('BAHARUNE')
                embed = bahaog(url=url, BAHAENUR=BAHAENUR,
                               BAHARUNE=BAHARUNE, sac_bh=sac_bh)
                await msg.channel.send(embed=embed)
                await msg.edit(suppress=True)
            if "https://nhentai.net/g/" in url:
                try:
                    server_id = msg.guild.id
                except:
                    server_id = None
                if is_embed_ban(server_id=server_id, arg="nh"):
                    continue
                digit, _ = extract_numbers(url)
                if digit != None:
                    with open('json/cookies.json', 'r', encoding='utf8') as file:
                        data = json.load(file)
                    cf_clearance = data["cf_clearance"]
                    csrftoken = data["csrftoken"]
                    embed = test_embed(
                        digit=digit, cf_clearance=cf_clearance, csrftoken=csrftoken)
                    if embed == 404:
                        await msg.channel.send("不存在")
                        return
                    elif embed == 403:
                        await msg.channel.send("存取遭拒")
                        return
                    view = NumberView(embed=embed)
                    await msg.channel.send(embed=embed, view=view)
                    await msg.edit(suppress=True)
                
            elif "wnacg.com" in url:
                try:
                    server_id = msg.guild.id
                except:
                    server_id = None
                if is_embed_ban(server_id=server_id, arg="wn"):
                    continue
                
                if "wnacg.com/photos-index-aid-" in url or "wnacg.com/photos-index-page-" in url or "wnacg.com/photos-slide-aid-" in url or "wnacg.com/photos-slist-aid-" in url:
                    try:
                        digit = url[url.rfind("-")+1:-5]
                        embed = create_wnacg_embed(digit=digit)
                        view2 = NumberView2(embed=embed)
                        await msg.channel.send(embed=embed, view=view2)
                        await msg.edit(suppress=True)
                    except:
                        pass
                elif "wnacg.com/?ctl=photos" in url or "wnacg.com/photos-view-id-" in url:
                    try:
                        digit = find_front_page(url)
                        embed = create_wnacg_embed(digit=digit)
                        view2 = NumberView2(embed=embed)
                        await msg.channel.send(embed=embed, view=view2)
                        await msg.edit(suppress=True)
                    except:
                        pass
                           
            elif "18comic.vip" in url or "18comic.org" in url or "18comic-16promax.com" in url:
                try:
                    server_id = msg.guild.id
                    channel_id = msg.channel.id
                except:
                    server_id = None
                if channel_id == 1294356961202147439:
                    continue
                if is_embed_ban(server_id=server_id, arg="jm"):
                    continue
                embed = jm_embed(url)
                view3 = NumberView3(embed=embed)
                await msg.channel.send(embed=embed,view=view3)

    if msg.author == bot.user:
        return
    elif "-1200" == msg.content:
        pu_lst = []
        current_pu = None
        with open('json/pu.json', 'r', encoding='utf8') as f:
            tdata = json.load(f)
        for key, value in tdata.items():
            if value == True:
                current_pu = key
                tdata.pop(key)
                break
        if check_lock(msg.channel.id):
            return
        if not assert_cooldown():
            return
        user_id = str(msg.author.id)
        with open('json/gacha.json', 'r', encoding='utf8') as file:
            data = json.load(file)
        try:
            user = data[user_id]
        except:
            data[user_id] = {"PU": 0, "SSR": 0, "SR": 0, "R": 0, "total": 0}
            user = data[user_id].copy()
        feed = ""
        stone = ""

        # 這裡是抽卡的機率設定，可以自行更改 (SSR, SR, R, PU)
        result = Gacha(3, 18.5, 78.5, [0.7])
        PU_count = 0

        # 此處emoji需自行更改成機器人可訪問的emoji
        for i in range(len(result)):
            if result[i] == 3:
                feed += "<:SSR:1075797390131911681>"
                stone += ":new:"
            elif result[i] == 2:
                feed += "<:SR:1075797417787662398>"
                stone += "<:moji:1075798877573230623>x10"
            elif result[i] == 1:
                feed += "<:R_:1075797383184646265>"
                stone += "<:moji:1075798877573230623>x1"
            elif result[i] == 4:
                feed += current_pu
                stone += ":new:"
            elif result[i] == 5:
                if current_pu == "<:hina_dress:1267744936103510038>":
                    key = random.choice(
                        [
                            "<:hoshino:1134070677515812924>",
                            "<:mika:1134070679394844703>",
                            "<:wakamon:1134070683303952466>",
                            "<:hanako_swimsuit:1267750062201769995>"
                        ]
                        )
                    if key == "<:hoshino:1134070677515812924>":
                        PU_count += 1
                else:
                    key = random.choice(
                        [
                            "<:hina_dress:1267744936103510038>",
                            "<:mika:1134070679394844703>",
                            "<:wakamon:1134070683303952466>",
                            "<:hanako_swimsuit:1267750062201769995>"
                        ]
                        )
                    if key == "<:hina_dress:1267744936103510038>":
                        PU_count += 1
                feed += key
                stone += ":new:"
            elif result[i] == 6:
                key = random.choice(list(tdata.keys()))
                feed += key
                stone += ":new:"
            if i == 4:
                feed += "\n"
                stone += "\n"
        SSR_count = result.count(3)+sum(result.count(i) for i in range(4, 25))
        SR_count = result.count(2)
        R_count = result.count(1)
        PU_count += result.count(4)
        user["PU"] += PU_count
        user["SSR"] += SSR_count
        user["SR"] += SR_count
        user["R"] += R_count
        user["total"] += 10
        data[user_id] = user.copy()
        with open('json/gacha.json', 'w', encoding='utf8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        await msg.channel.send("<:B_env:1076108979375185930>\n<:Arona:1076109041136316496>")
        await msg.channel.send("<:result:1076111748106571830>")
        await msg.channel.send(feed)
        await msg.channel.send(stone)

        # 此段為PU時發出的圖片，可自訂

        # if 4 in result:
            # if current_pu == "your pu emoji":
                # await msg.channel.send("image url")
            # else:
                # await msg.channel.send("image url")
        # if 5 in result:
            # await msg.channel.send("image url")
        # if 6 in result:
            # await msg.channel.send("image url")


        # if result.count(1) == 9 and result.count(2) == 1:
            # await msg.channel.send("image url")
    else:
        pass

    await bot.process_commands(msg)


@bot.tree.command(name="歡迎訊息", description="設定歡迎訊息(會在設定該指令的地方發出)")
@app_commands.describe(arg="內文")
async def welcome_msg(interaction: discord.Interaction, arg: str):
    server_id = str(interaction.guild_id)
    channel_id = interaction.channel.id
    with open('json/welcome.json', 'r', encoding='utf8') as file:
        data = json.load(file)
    data[server_id] = [arg, channel_id]
    with open('json/welcome.json', 'w', encoding='utf8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    await interaction.response.send_message("已設定")


async def load_extensions():
    for filename in os.listdir('./cmds'):
        if filename.endswith('.py'):
            await bot.load_extension(f'cmds.{filename[:-3]}')

with open('token.json', 'r', encoding='utf8') as file:
    data = json.load(file)


async def main():
    async with bot:
        await load_extensions()
        await bot.start(data["token"])

asyncio.run(main())
