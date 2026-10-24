# 各站本子 embed 換到指定頁：右鍵「跳轉頁數」與書籤共用。
# 依 embed 作者名稱分站，換好圖片與頁碼後回傳該站的翻頁 View。
import re

import discord

from functions.wnacg import get_page_image, apply_page, embed_thread_hint, NumberView2
from functions.nhentai import nh_page_image, nh_gallery, extract_numbers, NumberView
from functions.jm import extract_number_from_url, jm_page_image, jm_gallery, JM_COLOR, NumberView3
from functions.kemono import render_kemono_page, KemonoView
from functions.hitomi import render_hitomi_page, HitomiView
from functions.ehentai import render_ehentai_page, EHentaiView
from functions.cdn_pages import apply_page as apply_cdn_page, strip_fragment, total_pages, current_page

# 有翻頁功能的 embed（作者名稱）
PAGED_SITES = ("wnacg", "nhentai", "禁漫天堂", "kemono", "coomer", "hitomi", "E-Hentai", "ExHentai")


def is_paged(embed: discord.Embed):
    return bool(embed.author and embed.author.name in PAGED_SITES and total_pages(embed))


def paging_view(bot, embed: discord.Embed, page_num=None):
    """該站的翻頁 View，中間按鈕顯示「目前頁/總頁數」"""
    name = embed.author.name
    if name == "wnacg":
        view = NumberView2(session=bot.session)
    elif name == "nhentai":
        view = NumberView(session=bot.session, sec5h=bot.missav_crawl)
    elif name == "hitomi":
        view = HitomiView(session=bot.session)
    elif name in ("E-Hentai", "ExHentai"):
        view = EHentaiView(session=bot.session)
    elif name in ("kemono", "coomer"):
        view = KemonoView(session=bot.session)
    else:  # 禁漫天堂
        view = NumberView3()
    view.middle_button.label = f"{page_num or current_page(embed)}/{total_pages(embed)}"
    return view


async def render_page(bot, embed: discord.Embed, target_page):
    """把 embed 換到第 target_page 頁（直接修改 embed），回傳 (是否拿到圖, 翻頁 View)。"""
    page = total_pages(embed)
    name = embed.author.name
    cdn = getattr(bot, 'image_cdn', None)
    if name == "wnacg":
        digit = re.search(r"aid-(\d+)\.html", embed.url).group(1)
        img = await get_page_image(bot.session, cdn, digit, target_page, page=page,
                                   thread_hint=embed_thread_hint(embed), inline=True)
        apply_page(embed, img, target_page, cdn, digit)

    elif name == "nhentai":
        number = extract_numbers(strip_fragment(embed.url))[0]
        img = await nh_page_image(bot.session, bot.missav_crawl, cdn, number, target_page,
                                  thread_hint=embed_thread_hint(embed), inline=True)
        apply_cdn_page(embed, img, target_page, cdn, nh_gallery(number))

    elif name == "hitomi":
        await render_hitomi_page(bot.session, cdn, embed, target_page)
        img = embed.image.url

    elif name in ("E-Hentai", "ExHentai"):
        await render_ehentai_page(bot.session, cdn, embed, target_page)
        img = embed.image.url

    elif name in ("kemono", "coomer"):
        await render_kemono_page(bot.session, cdn, embed, target_page)
        img = embed.image.url

    else:  # 禁漫天堂
        id = extract_number_from_url(strip_fragment(embed.url))
        img = await jm_page_image(cdn, id, target_page, total=page, thread_hint=embed_thread_hint(embed),
                                  inline=True)
        apply_cdn_page(embed, img, target_page, cdn, jm_gallery(id), colour=JM_COLOR)

    return bool(img), paging_view(bot, embed, target_page)
