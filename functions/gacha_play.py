# 抽卡的呈現：一次十連只用一則訊息，原地編輯、一行一行往下加：信封＋阿羅娜 → 結果單 → 卡片，
# 最後在下方加上青輝石與 PU 展示，好幾個人同時抽也不會互相穿插。
# 附「再抽十連」按鈕（persistent，重開機後舊訊息也能按）。
import asyncio
import io

import discord

from functions.app_emoji import app_emojis
from functions.ba_banner import pu_student_id, pu_showcase, pu_showcase_image
from functions.gacha import process_gacha_data, CHARGE_PU
from functions.slot import block_check

# 每一步停多久（秒）；編輯訊息每 5 秒約 5 次上限，一次十連 1 則＋2 次編輯
STEP_DELAY = 0.6
# 依序出現的前幾步（之後加上卡片）：信封跟阿羅娜同時出現，再來是結果單。
# 整則訊息只有表情（不超過 30 個）Discord 才會放大顯示，所以青輝石那行（有「x10」文字）放在 embed
INTRO_STEPS = ["<:B_env:1076108979375185930>\n<:Arona:1076109041136316496>", "<:result:1076111748106571830>"]
GACHA_COLOR = 0x3498DB
# 舊格式的卡池（不是 ba_<學生 ID> 表情）抽到 PU 時貼的影片
LEGACY_PU_VIDEO = "https://cdn.discordapp.com/attachments/1149330986279108689/1171035321736110100/6bd4b9604ac8b986.mp4"
# 九張 R＋一張 SR 時附的圖
ALL_R_IMAGE = "https://media1.tenor.com/m/Yo7MG1aUbOgAAAAd/9%E8%97%8D1%E9%87%91.gif"  # 9藍1金.gif


async def _pu_embed(bot, pu):
    """抽到 PU 的展示卡（紀念大廳或立繪）與要附上的圖檔：回傳 (embed, File 或 None)；
    舊格式卡池或查詢失敗回傳 None。圖片由 bot 下載後附在訊息上（Discord 自己去抓有時會抓不到），
    下載失敗才退回用網址。"""
    student_id = pu_student_id(pu)
    if student_id is None:
        return None
    try:
        name, url = await pu_showcase(bot.session, student_id)
    except Exception as e:
        print(f"[ba] PU 展示 {student_id} 失敗: {e!r}", flush=True)
        return None
    embed = discord.Embed(title=f"🎉 抽到 PU：{name}", color=GACHA_COLOR)
    try:
        data, ext = await pu_showcase_image(bot.session, student_id, url)
    except Exception as e:
        print(f"[ba] 下載 PU 圖片 {student_id} 失敗，改用網址: {e!r}", flush=True)
        return embed.set_image(url=url), None
    filename = f"pu_{student_id}{ext}"
    return embed.set_image(url=f"attachment://{filename}"), discord.File(io.BytesIO(data), filename=filename)


async def play_gacha(bot, user_id, channel_id, send_first):
    """抽一次十連並播出來。send_first(內容) 送出第一則訊息並回傳 Message，之後都編輯這則。
    回傳 "lock"（頻道上鎖）、None（沒抽）或最後的 Message。"""
    data, status = process_gacha_data(user_id, channel_id)
    if status == "lock":
        return "lock"
    if not data:
        return None
    # 圖示換成機器人的應用程式表情（同名），伺服器表情在機器人不在的伺服器顯示不出來
    fix = app_emojis(bot).fix
    result = data["result"]
    # 查紀念大廳跟動畫同時進行
    showcase = asyncio.ensure_future(_pu_embed(bot, data.get("pu"))) if 4 in result else None

    lines = [fix(INTRO_STEPS[0])]
    message = await send_first(lines[0])
    for line in INTRO_STEPS[1:]:
        await asyncio.sleep(STEP_DELAY)
        lines.append(fix(line))
        await message.edit(content="\n".join(lines))
    await asyncio.sleep(STEP_DELAY)

    # 卡片放在文字（只有表情時 Discord 會放大顯示），青輝石放在 embed
    embeds = [discord.Embed(description=fix(data["stone"]), color=GACHA_COLOR)]
    if data.get("new_system"):
        labels = {"PU": "PU 保底", "SSR_PU": "★3 保底，抽中 PU", "SSR": "★3 保底，沒中 PU"}
        notes = [f"第 {n} 抽 {labels[kind]}" for n, kind in data.get("triggered") or []]
        embeds[0].set_footer(text="・".join([f"招募充能 {data.get('charge', 0)}/{CHARGE_PU}"] + notes))
    else:
        embeds[0].set_footer(text=f"總抽數 {data.get('total', 0)}（{data.get('total', 0) // 200} 井）")
    if result.count(1) == 9 and result.count(2) == 1:
        embeds.append(discord.Embed(color=GACHA_COLOR).set_image(url=ALL_R_IMAGE))
    lines.append(fix(data["feed"]))
    # 紀念大廳查好了就一起放；還沒好就先出卡片，查好再補上，動畫不等它
    if showcase is not None and showcase.done():
        await _add_showcase(message, lines, embeds, showcase.result(), first=True)
    else:
        await message.edit(content="\n".join(lines), embeds=embeds, view=GachaAgainView())
        if showcase is not None:
            await _add_showcase(message, lines, embeds, await showcase)
    return message


async def _add_showcase(message, lines, embeds, showcase, first=False):
    if showcase is None:
        if first:
            await message.edit(content="\n".join(lines), embeds=embeds, view=GachaAgainView())
        await message.channel.send(LEGACY_PU_VIDEO)  # 舊格式卡池：影片沒辦法放進 embed
        return
    pu_embed, file = showcase
    embeds.insert(1, pu_embed)
    await message.edit(content="\n".join(lines), embeds=embeds, view=GachaAgainView(),
                       **({"attachments": [file]} if file else {}))


class GachaAgainView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="再抽十連", style=discord.ButtonStyle.primary, custom_id="gacha:again")
    async def again(self, interaction: discord.Interaction, button: discord.ui.Button):
        if block_check(interaction.channel_id):
            return await interaction.response.send_message("這個頻道不能抽卡。", ephemeral=True)

        async def send_first(content):
            await interaction.response.send_message(content)
            return await interaction.original_response()

        status = await play_gacha(interaction.client, interaction.user.id, interaction.channel_id, send_first)
        if status == "lock" and not interaction.response.is_done():
            await interaction.response.send_message("這個頻道的抽卡已上鎖。", ephemeral=True)
